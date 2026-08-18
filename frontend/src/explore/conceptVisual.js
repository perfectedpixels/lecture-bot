// Maps the concept taxonomy from src/explore_topic.py (CONCEPT_TAXONOMY) to an
// icon + accent color. Keep this list in sync with that module — the backend
// only ever tags cards with these values.
import {
  BookOpen,
  LayoutGrid,
  Briefcase,
  Compass,
  Tag,
  Clock,
  CheckCircle2,
  Scale,
  Sparkles,
} from 'lucide-react'

// The two most common tags use the app's own brand accents (the lavender/
// violet from the Streamlit UI's #9D4EDD/#8938f6 family) so the dominant
// on-screen colors read as on-brand; rarer tags get complementary accents
// purely for scannability/differentiation.
const VISUALS = {
  lecture_concept: { icon: BookOpen, color: '#9D4EDD', label: 'Lecture concept' },
  methodology: { icon: Compass, color: '#8938f6', label: 'Methodology' },
  framework: { icon: LayoutGrid, color: '#38bdf8', label: 'Framework' },
  case_study: { icon: Briefcase, color: '#2dd4bf', label: 'Case study' },
  terminology: { icon: Tag, color: '#E0B0FF', label: 'Terminology' },
  historical_example: { icon: Clock, color: '#fbbf24', label: 'Historical example' },
  best_practice: { icon: CheckCircle2, color: '#34d399', label: 'Best practice' },
  ethics: { icon: Scale, color: '#fb7185', label: 'Ethics' },
}

const GENERAL_VISUAL = { icon: Sparkles, color: '#c9b8dd', label: 'General knowledge' }

export function conceptVisual(concepts, grounded) {
  if (!grounded) return GENERAL_VISUAL
  const match = (concepts || []).find((c) => VISUALS[c])
  return match ? VISUALS[match] : { ...GENERAL_VISUAL, label: 'Lecture concept' }
}
