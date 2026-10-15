# 受约束ADR: ADR-012/013/014 (all revised, AUDIT-FIX applied)
# 演示目标: 复现TC-006(用户输入→L1高置信路由→L2儿童发热首轮响应)
#         及TC-015(追问回答→L2采集)
# 修订版本: v1.0-audit-fix-20260619

from __future__ import annotations

from workflow.orchestrator import Orchestrator


def main() -> None:
    orch = Orchestrator()

    print("=" * 60)
    print("TC-006: 用户输入 → L1高置信路由 → L2儿童发热首轮响应")
    print("=" * 60)

    sid = orch.new_session()
    print(f"[系统] 会话创建: {sid}")

    result_tc006 = orch.process_message(
        sid,
        "孩子两岁半，昨天开始发烧38.5度，精神还行，喝水正常",
    )
    print(f"[L0+L1] next_action={result_tc006['next_action']}")
    print(f"[L2 首轮提问]\n{result_tc006['response']}")
    state = orch._sessions[sid]
    scenario_ctx = state.scenario_context
    if scenario_ctx:
        print(f"[场景注入] scenario_id={scenario_ctx.scenario_id}, "
              f"confidence={scenario_ctx.route_confidence}, "
              f"intent_category={scenario_ctx.intent_category}")
    print(f"[State] conversation_stage={state.conversation_stage.value}, "
          f"round_count={state.round_count}, "
          f"is_emergency={state.is_emergency}, "
          f"red_flag_level={state.red_flag_level}")

    print()
    print("=" * 60)
    print("TC-015: 追问回答 → L2采集 → 检查termination")
    print("=" * 60)

    result_tc015 = orch.process_follow_up(
        sid,
        "两岁半，最高38.5度，耳温枪测的，精神很好能玩玩具，喝水正常，发烧昨天开始的",
    )
    print(f"[L0] 安全放行, next_action={result_tc015['next_action']}")
    if result_tc015["next_action"] != "completed":
        print(f"[L2 追问]\n{result_tc015['response']}")
    state2 = orch._sessions[sid]
    print(f"[State] conversation_stage={state2.conversation_stage.value}, "
          f"round_count={state2.round_count}")
    print(f"[Collected Facts] {dict(state2.collected_facts)}")

    if state2.conversation_stage.value == "assessing":
        scenario = __import__(
            "workflow.scenarios.pediatric_fever.scenario", fromlist=["PediatricFeverScenario"]
        ).PediatricFeverScenario()
        filled = scenario.fill_defaults(state2)
        assessment = orch._build_assessment(filled)
        print(f"\n[L2 评估完成]\n{assessment['response']}")

    print()
    print("=" * 60)
    print("审计日志")
    print("=" * 60)
    for i, entry in enumerate(orch.audit_log):
        print(f"[{i+1}] event_type={entry.event_type}, "
              f"agent_name={entry.agent_name}, "
              f"red_flag_triggered={entry.red_flag_triggered}, "
              f"created_at={entry.created_at}")

    print()
    print("TC-006 + TC-015 链路验证完成")


if __name__ == "__main__":
    main()
