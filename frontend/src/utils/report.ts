/** 解析诊断报告纯文本 → 结构化 HTML */
export function parseReport(text: string): string {
  const esc = (s: string) =>
    s.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')

  // 按双换行分段
  const paras = text.split(/\n\n+/).filter(p => p.trim())
  if (paras.length <= 1) {
    return (
      '<div class="report-title text-center font-brand text-lg font-semibold text-blue-dark border-b border-lilac-light pb-2.5 mb-4">诊断报告</div>' +
      '<p>' + esc(text).replace(/\n/g, '<br>') + '</p>'
    )
  }

  let html =
    '<div class="report-title text-center font-brand text-lg font-semibold text-blue-dark border-b border-lilac-light pb-2.5 mb-4">诊断报告</div>'

  paras.forEach(p => {
    const trimmed = p.trim()
    // 检测免责声明段落
    if (/免责声明|不能替代|仅供参考|及时就医/.test(trimmed)) {
      html +=
        '<div class="disclaimer mt-3 pt-2.5 border-t border-lilac-light text-sm text-mauve leading-relaxed">⚕&nbsp;' +
        esc(trimmed).replace(/\n/g, '<br>') +
        '</div>'
    } else {
      html += '<p class="mb-2.5 text-sm leading-relaxed">' + esc(trimmed).replace(/\n/g, '<br>') + '</p>'
    }
  })

  return html
}

/** 检测文本是否包含诊断报告特征 */
export function isReportContent(content: string, options?: unknown[]): boolean {
  return (!options || options.length === 0) && content.length > 150
}
