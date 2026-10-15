/**
 * PII 预脱敏工具 — 在用户输入进入 LangGraph 前执行
 * 安全红线 #4: "用户输入进入 LangGraph 前必须完成姓名/身份证/手机号脱敏"
 */

/** 中国身份证号正则 (18位 + 17位+X) */
const ID_CARD_RE = /\b[1-9]\d{5}(?:19|20)\d{2}(?:0[1-9]|1[0-2])(?:0[1-9]|[12]\d|3[01])\d{3}[\dXx]\b/g

/** 中国大陆手机号正则 */
const PHONE_RE = /\b1[3-9]\d{9}\b/g

/** 中国固定电话正则 */
const LANDLINE_RE = /\b(?:0\d{2,3}-)?\d{7,8}\b/g

/** 常见中文姓名模式（2-4字中文） — 启发式，有误伤风险，仅在与其他 PII 出现时触发 */
const NAME_PATTERNS = [
  // 显式姓名标签
  /(?:姓名|名字|我叫|我是|患者|病人)[:：\s]*([一-龥]{2,4})/g,
  // 身份证号/手机号通常伴随姓名
]

/**
 * 对用户输入文本执行 PII 脱敏
 * @returns 脱敏后的文本
 */
export function maskPII(text: string): string {
  let result = text

  // 1. 身份证号 → [身份证已隐藏]
  result = result.replace(ID_CARD_RE, '[身份证已隐藏]')

  // 2. 手机号 → [手机号已隐藏]
  result = result.replace(PHONE_RE, '[手机号已隐藏]')

  // 3. 固定电话 → [电话已隐藏]
  result = result.replace(LANDLINE_RE, '[电话已隐藏]')

  // 4. 显式姓名标签 → 替换姓名为 [姓名已隐藏]
  for (const pattern of NAME_PATTERNS) {
    result = result.replace(pattern, (_full, name: string) => {
      return _full.replace(name, '[姓名已隐藏]')
    })
  }

  return result
}

/**
 * 检测文本是否包含未脱敏的 PII
 * @returns true 如果包含疑似 PII
 */
export function hasPII(text: string): boolean {
  return ID_CARD_RE.test(text) || PHONE_RE.test(text)
}
