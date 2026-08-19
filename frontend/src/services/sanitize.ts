// v9.24: 统一 HTML 消毒（防 XSS——所有 v-html 渲染前必须过这里）
import DOMPurify from 'dompurify'

export function sanitizeHtml(html: string): string {
  if (!html) return ''
  return DOMPurify.sanitize(html, {
    // 允许 mark 高亮 + 基础内联样式（墨题短文渲染需要）
    ALLOWED_TAGS: ['p', 'br', 'strong', 'em', 'mark', 'span', 'div', 'b', 'i', 'ul', 'ol', 'li', 'h1', 'h2', 'h3', 'blockquote', 'code', 'pre'],
    ALLOWED_ATTR: ['class', 'style'],
  })
}
