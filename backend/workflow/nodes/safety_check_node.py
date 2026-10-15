from safety.l0_filter import run_l0_filter
from safety.content_filter import check_medical_advice_compliance
from workflow.nodes._shared import msg_role, msg_content


async def safety_check_node(state: dict) -> dict:
    messages = state.get("messages", [])
    content = ""
    last_user_msg = None
    for msg in reversed(messages):
        if msg_role(msg) == "user":
            content = msg_content(msg)
            last_user_msg = msg
            break

    safety_checks_passed = True
    red_flag_raised = False
    red_flag_level = None
    blocked = False
    next_stage = None
    output = ""

    if content:
        l0_result = run_l0_filter(content, session_id=state.get("session_id", ""))
        red_flag_raised = l0_result.is_emergency
        red_flag_level = l0_result.red_flag_level

        if red_flag_raised:
            safety_checks_passed = False
            next_stage = "emergency"
            output = l0_result.response or "您描述的症状需要立即就医。请立即拨打120急救电话，保持冷静，不要自行驾车。"
        else:
            # NOTE: We mutate messages in-place rather than returning them in the dict
            # because LangGraph's add_messages reducer appends new entries. In-place
            # mutation is safe here since the same list object is passed by reference
            # to downstream nodes, and the checkpointer snapshots post-mutation state.
            masked_content = getattr(l0_result, 'response', '')
            if masked_content and last_user_msg is not None:
                if isinstance(last_user_msg, dict):
                    last_user_msg["content"] = masked_content
                elif hasattr(last_user_msg, "content"):
                    last_user_msg.content = masked_content
                content = masked_content

            compliance_result = check_medical_advice_compliance(content)
            if compliance_result.get("blocked"):
                blocked = True
                output = compliance_result.get("output", "请咨询医生")

    return {
        "safety_checks_passed": safety_checks_passed,
        "red_flag_raised": red_flag_raised,
        "red_flag_level": red_flag_level,
        "blocked": blocked,
        "next_stage": next_stage,
        "output": output,
    }
