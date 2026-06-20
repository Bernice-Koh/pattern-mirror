import { Extension } from '@tiptap/core'
import type { EditorView } from '@tiptap/pm/view'
import { Decoration, DecorationSet } from '@tiptap/pm/view'
import { Plugin, PluginKey } from '@tiptap/pm/state'
import type { Node as ProseMirrorNode } from '@tiptap/pm/model'
import type { CitedFlag } from '@/lib/analyze-contract'

export const flagDecorationsKey = new PluginKey<DecorationSet>(
  'flagDecorations',
)

/** Offsets index the plaintext; a single leading text block puts character N at
 *  document position N + 1. Ranges that fall outside the doc are skipped so a
 *  stale analysis pass can never throw against freshly edited text. */
function buildDecorations(
  doc: ProseMirrorNode,
  flags: CitedFlag[],
): DecorationSet {
  const decorations: Decoration[] = []
  for (const flag of flags) {
    const from = flag.start_offset + 1
    const to = flag.end_offset + 1
    if (from < 1 || to > doc.content.size || from >= to) continue
    decorations.push(
      Decoration.inline(from, to, {
        class: 'flag-dict',
        'data-flag-id': flag.id,
      }),
    )
  }
  return DecorationSet.create(doc, decorations)
}

/** Hand the latest flags to the decoration plugin without mutating the document. */
export function applyFlags(view: EditorView, flags: CitedFlag[]): void {
  view.dispatch(view.state.tr.setMeta(flagDecorationsKey, flags))
}

/** Paints inline underlines from the analyze response; between passes it maps the
 *  existing decorations through edits so they track the words they mark. */
export const FlagDecorations = Extension.create({
  name: 'flagDecorations',

  addProseMirrorPlugins() {
    return [
      new Plugin<DecorationSet>({
        key: flagDecorationsKey,
        state: {
          init: () => DecorationSet.empty,
          apply(tr, current) {
            const flags = tr.getMeta(flagDecorationsKey) as
              | CitedFlag[]
              | undefined
            if (flags) return buildDecorations(tr.doc, flags)
            return current.map(tr.mapping, tr.doc)
          },
        },
        props: {
          decorations(state) {
            return flagDecorationsKey.getState(state)
          },
        },
      }),
    ]
  },
})
