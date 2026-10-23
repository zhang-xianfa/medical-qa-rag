/** 诊断报告解析：纯文本 → 带小标题的 HTML 片段 */

export type RiskLevel = 'low' | 'mid' | 'high' | null

const esc = (s: string) =>
  s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

/** 从报告文本里识别风险等级 */
export function detectRisk(text: string): RiskLevel {
  // 只认风险分级本身的措辞；"请立即就医"经常出现在危险信号段落里，
  // 不能拿它当高风险，否则中度病例也会被标成高风险。
  if (/(重度|高风险|高危|危及生命)/.test(text)) return 'high'
  if (/(中度|中风险|中等风险)/.test(text)) return 'mid'
  if (/(轻度|低风险|较低风险)/.test(text)) return 'low'
  return null
}

export const RISK_LABEL: Record<Exclude<RiskLevel, null>, string> = {
  low: '低风险',
  mid: '中风险',
  high: '高风险',
}

/** 段落 → 小标题（按常见的报告行文习惯匹配） */
const SECTION_RULES: Array<{ re: RegExp; title: string }> = [
  { re: /鉴别诊断|需要排除|还需排除/, title: '鉴别诊断' },
  { re: /风险|严重程度|紧急程度/, title: '风险评估' },
  { re: /建议|处理|措施|护理/, title: '建议措施' },
  { re: /危险信号|警惕|就医指征|何时就医/, title: '危险信号' },
  { re: /^(根据|综合|从您|结合)/, title: '初步分析' },
]

export function parseReport(text: string): string {
  const paras = text.split(/\n\n+/).map(p => p.trim()).filter(Boolean)
  if (paras.length <= 1) {
    return '<p class="text-[15px] leading-7 text-eggplant/80">' +
      esc(text).replace(/\n/g, '<br>') + '</p>'
  }

  const used = new Set<string>()
  let html = ''

  for (const para of paras) {
    // 免责声明单独成块
    if (/免责声明|不能替代专业|仅供参考/.test(para) && para.length < 150) {
      html += '<div class="disclaimer mt-4 text-xs leading-relaxed">' +
        esc(para).replace(/\n/g, '<br>') + '</div>'
      continue
    }

    const hit = SECTION_RULES.find(r => r.re.test(para) && !used.has(r.title))
    if (hit) {
      used.add(hit.title)
      html += '<div class="report-section-title">' + hit.title + '</div>'
    }

    html += '<p class="mt-1.5 text-[14px] leading-7 text-eggplant/80">' +
      esc(para).replace(/\n/g, '<br>') + '</p>'
  }

  return html
}

/** 检测文本是否包含诊断报告特征 */
export function isReportContent(content: string, options?: unknown[]): boolean {
  return (!options || options.length === 0) && content.length > 150
}
