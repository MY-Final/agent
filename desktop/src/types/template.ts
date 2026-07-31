import type { SectionDefinition } from './results'

export interface ParseTemplateRecord {
  id: string
  name: string
  description: string | null
  version: string
  sections: SectionDefinition[]
  is_default: boolean
  created_at: string
  updated_at: string
}

export interface ParseTemplateInput {
  name: string
  description?: string | null
  version: string
  sections: SectionDefinition[]
  is_default?: boolean
}

export interface TemplateDraft {
  name: string
  description: string
  version: string
  is_default: boolean
  sections: SectionDefinition[]
}

export interface TemplateSuggestionInput {
  description: string
  reference_text?: string | null
}

export interface TemplateSuggestion {
  suggested_name: string
  description: string | null
  sections: SectionDefinition[]
}
