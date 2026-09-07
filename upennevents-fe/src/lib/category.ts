import type { ApiEvent } from "../types/event";

/**
 * Categories are the real Penn school/division taxonomy, not a guess: they
 * come from `event.school_division`, which is `calendars.school_division`
 * from the original penn-calendars.csv registry, joined in by
 * alembic/versions/0003_events_school_division.py. An earlier version of
 * this file derived categories from event tags instead, which produced a
 * taxonomy that didn't match Penn's actual school list -- this is the fix.
 *
 * CATEGORY_ORDER's 12 schools match the official undergraduate + graduate/
 * professional school list; the remaining keys cover registry divisions
 * that aren't one of the 12 schools (Athletics, Student Life, everything
 * else university-wide) plus a fallback for events with no calendar link.
 */
export type CategoryKey =
  | "sas"
  | "wharton"
  | "seas"
  | "nursing"
  | "annenberg"
  | "gse"
  | "law"
  | "medicine"
  | "dental"
  | "sp2"
  | "vet"
  | "design"
  | "athletics"
  | "student_life"
  | "university_wide"
  | "other";

export interface CategoryMeta {
  key: CategoryKey;
  /** Full official name, for the legend and the school filter dropdown. */
  label: string;
  /** Short form, for space-constrained chips. */
  shortLabel: string;
}

export const CATEGORY_ORDER: CategoryMeta[] = [
  { key: "sas", label: "School of Arts & Sciences (The College)", shortLabel: "Arts & Sciences" },
  { key: "wharton", label: "The Wharton School", shortLabel: "Wharton" },
  { key: "seas", label: "School of Engineering and Applied Science (Penn Engineering)", shortLabel: "Engineering" },
  { key: "nursing", label: "School of Nursing", shortLabel: "Nursing" },
  { key: "annenberg", label: "Annenberg School for Communication", shortLabel: "Annenberg" },
  { key: "gse", label: "Graduate School of Education (Penn GSE)", shortLabel: "Penn GSE" },
  { key: "law", label: "Penn Carey Law", shortLabel: "Penn Carey Law" },
  { key: "medicine", label: "Perelman School of Medicine", shortLabel: "Perelman Medicine" },
  { key: "dental", label: "School of Dental Medicine (Penn Dental)", shortLabel: "Penn Dental" },
  { key: "sp2", label: "School of Social Policy & Practice (SP2)", shortLabel: "SP2" },
  { key: "vet", label: "School of Veterinary Medicine (Penn Vet)", shortLabel: "Penn Vet" },
  { key: "design", label: "Stuart Weitzman School of Design", shortLabel: "Weitzman Design" },
  { key: "athletics", label: "Athletics", shortLabel: "Athletics" },
  { key: "student_life", label: "Student Life", shortLabel: "Student Life" },
  { key: "university_wide", label: "University-Wide", shortLabel: "University-Wide" },
  { key: "other", label: "Other", shortLabel: "Other" },
];

const CATEGORY_META: Record<CategoryKey, CategoryMeta> = Object.fromEntries(
  CATEGORY_ORDER.map((c) => [c.key, c])
) as Record<CategoryKey, CategoryMeta>;

// calendars.school_division values (see docker compose exec db psql ... GROUP
// BY school_division) mapped onto the taxonomy above. Divisions that aren't
// one of the 12 schools and aren't Athletics/Student Life fall into
// "university_wide" -- they're real university offices (Provost, HR,
// Libraries, ...), just not degree-granting schools.
const SCHOOL_DIVISION_TO_CATEGORY: Record<string, CategoryKey> = {
  SAS: "sas",
  Arts: "sas",
  Wharton: "wharton",
  Engineering: "seas",
  Nursing: "nursing",
  Annenberg: "annenberg",
  GSE: "gse",
  Law: "law",
  Medicine: "medicine",
  "Penn Medicine": "medicine",
  Dental: "dental",
  SP2: "sp2",
  Vet: "vet",
  Design: "design",
  Athletics: "athletics",
  "University Life": "student_life",
  "College Houses": "student_life",
  University: "university_wide",
  Libraries: "university_wide",
  "Penn Global": "university_wide",
  Provost: "university_wide",
  "Business Services": "university_wide",
  HR: "university_wide",
  Museum: "university_wide",
  SRFS: "university_wide",
  Admissions: "university_wide",
  Alumni: "university_wide",
};

export function deriveCategory(schoolDivision: string | null): CategoryKey {
  if (!schoolDivision) return "other";
  return SCHOOL_DIVISION_TO_CATEGORY[schoolDivision] ?? "other";
}

export function categoryLabel(key: CategoryKey): string {
  return CATEGORY_META[key].label;
}

export function categoryShortLabel(key: CategoryKey): string {
  return CATEGORY_META[key].shortLabel;
}

export function eventCategory(event: Pick<ApiEvent, "school_division">): CategoryKey {
  return deriveCategory(event.school_division);
}

// Colors are computed rather than hand-declared per category: at 16
// categories, a hand-maintained CSS class per (category x usage) pair
// (event pill, week block, row accent, chip, legend dot) would be 80+ rules
// to keep in sync. Hues are spread evenly around the wheel in CATEGORY_ORDER
// order, using the same lightness/chroma recipe as the original design
// mockup's hand-picked category colors.
export function categoryCssVars(key: CategoryKey): Record<string, string> {
  const idx = CATEGORY_ORDER.findIndex((c) => c.key === key);
  const hue = Math.round((idx * 360) / CATEGORY_ORDER.length);
  return {
    "--cat-main": `oklch(56% 0.11 ${hue})`,
    "--cat-bg": `oklch(94% 0.025 ${hue})`,
    "--cat-solid": `oklch(41% 0.115 ${hue})`,
  };
}
