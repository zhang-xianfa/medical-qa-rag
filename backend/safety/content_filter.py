import re

"""
医疗建议合规过滤
职责：防止系统输出具体用药剂量，确保合规性
使用场景：诊断Agent生成输出后，检查是否包含违规剂量信息
"""

_DOSE_PATTERN = re.compile(r'\d+\s*(?:mg|片|粒|ml|毫升|毫克|微克|g|克)')

_COMPLIANCE_PHRASE = '请咨询医生'

_DOSAGE_QUERY_INDICATORS = ['几片', '几粒', '多少毫克', '剂量', '两片']


def check_medical_advice_compliance(user_query, existing_output=None):
    if existing_output is not None:
        if _DOSE_PATTERN.search(existing_output):
            return {'blocked': True, 'output': _COMPLIANCE_PHRASE}
        return {'blocked': False, 'output': existing_output}

    is_dosage = any(indicator in user_query for indicator in _DOSAGE_QUERY_INDICATORS)

    if is_dosage:
        return {'blocked': True, 'output': _COMPLIANCE_PHRASE}

    return {'blocked': False, 'output': ''}
