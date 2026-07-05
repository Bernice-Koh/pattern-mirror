import { describe, it, expect, afterEach } from 'vitest'
import { Editor } from '@tiptap/core'
import StarterKit from '@tiptap/starter-kit'
import type { CitedFlag, FlagSourceStage } from '@/lib/analyze-contract'
import { applyFlags, FlagDecorations } from './flag-decorations'

const CITATION: CitedFlag['citation'] = {
  source_type: 'tafep',
  title: 'TAFEP Guidelines',
  reference: 'TAFEP-2024',
  publication_year: 2024,
  finding: null,
}

function makeFlag(
  id: string,
  source_stage: FlagSourceStage,
  start_offset: number,
  end_offset: number,
): CitedFlag {
  return {
    id,
    source_stage,
    category: 'gender',
    raw_span: '',
    start_offset,
    end_offset,
    explanation: '',
    citation: CITATION,
  }
}

let editor: Editor

function renderFlags(content: string, flags: CitedFlag[]): Editor {
  editor = new Editor({ extensions: [StarterKit, FlagDecorations], content })
  applyFlags(editor.view, flags)
  return editor
}

describe('flag decorations', () => {
  afterEach(() => {
    editor?.destroy()
  })

  it('underlines a dictionary flag with the solid-red class', () => {
    const { view } = renderFlags('an aggressive leader', [
      makeFlag('f1', 'dictionary', 14, 20),
    ])

    const span = view.dom.querySelector('.flag-dict')
    expect(span?.textContent).toBe('leader')
    expect(view.dom.querySelector('.flag-context')).toBeNull()
  })

  it('underlines a contextual flag with the dashed-amber class', () => {
    const { view } = renderFlags('an aggressive leader', [
      makeFlag('f2', 'contextual', 3, 13),
    ])

    const span = view.dom.querySelector('.flag-context')
    expect(span?.textContent).toBe('aggressive')
    expect(view.dom.querySelector('.flag-dict')).toBeNull()
  })

  it('renders dictionary and contextual flags with distinct classes together', () => {
    const { view } = renderFlags('an aggressive leader', [
      makeFlag('f1', 'dictionary', 14, 20),
      makeFlag('f2', 'contextual', 3, 13),
    ])

    expect(view.dom.querySelector('.flag-dict')?.textContent).toBe('leader')
    expect(view.dom.querySelector('.flag-context')?.textContent).toBe(
      'aggressive',
    )
  })

  it('skips a flag whose span falls outside the current document', () => {
    const { view } = renderFlags('short', [makeFlag('f3', 'contextual', 3, 99)])

    expect(view.dom.querySelector('.flag-context')).toBeNull()
  })
})
