export const REVEAL_FINAL_STATE_CSS =
  '[data-reveal="pop"]{opacity:1!important;transform:none!important}' +
  '[data-reveal="grow-y"]{transform:none!important}' +
  '[data-reveal="scale-x"]{transform:scaleX(var(--sx))!important}' +
  '[data-reveal="slide"]{transform:translateX(var(--x))!important}';

export function RevealNoScriptFallback() {
  return <noscript dangerouslySetInnerHTML={{ __html: `<style>${REVEAL_FINAL_STATE_CSS}</style>` }} />;
}
