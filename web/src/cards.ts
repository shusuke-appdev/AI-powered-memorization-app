export const subjects = ['民法', '商法', '刑法', '憲法', '行政法', '民事訴訟法', '刑事訴訟法', 'その他'];
export const types = ['規範', '判例', '類型', '知識'];
export const ranks = ['A+', 'A', 'B+', 'B', 'C'];
export const noBlanks = (type: string | null) => type === '知識' || type === '類型';

export type Hole = { hole: number; answer: string };
export type Segment = string | Hole;
export type Grade = 0 | 2 | 3 | 4 | 5;
export type Variant = { question: string; answer: string; layout: Segment[]; blank_count: number };
export type Source = {
  id: string; title: string | null; source_text: string; category: string | null;
  card_type: string | null; study_tags: string[]; study_version: string;
  study_favorite: boolean;
};
export type Card = Omit<Variant, 'layout'> & {
  id: string; source_id: string | null; title: string | null; category: string | null;
  card_type: string | null; rank: string | null; is_favorite: boolean;
  ease_factor: number | null; repetitions: number | null; interval: number | null;
  next_review: string | null; study_layout: Segment[] | null; study_version: string;
  study_tags: string[]; study_archived_at: string | null;
};
export type StudyTarget = {
  id: string; version: string; next_review: string; interval: number;
  ease_factor: number; repetitions: number; seen_holes: number[];
};
export type Assignment = {
  target_id: string; day: string; card_id: string; version: string; position: number;
  title: string; category: string; card_type: string | null; rank: string;
  layout: Segment[]; answer: string; grades: Record<string, Grade>;
  revision: number; completed_at: string | null; next_review: string | null;
  retried: number[];
};
export type Preset = {id: string; name: string; filters: Filters};
export type Library = {
  sources: Source[]; cards: Card[]; targets: StudyTarget[]; history: Assignment[];
  presets: Preset[]; quota: number;
};
export type Daily = {day: string; assignments: Assignment[]; unassigned: number};
export type Filters = {
  subjects: string[]; tags: string[]; ranks: string[]; types: string[];
  favorite: boolean; query: string; mode: 'range' | 'priority' | 'weak' | 'test';
  limit: number;
};
export const defaults: Filters = {
  subjects: [], tags: [], ranks: [], types: [], favorite: false, query: '', mode: 'range', limit: 10,
};
export const grades: { value: Grade; label: string }[] = [
  {value: 4, label: '◯ 完全に覚えていた'},
  {value: 2, label: '△ 不十分'},
  {value: 0, label: '× 忘れていた'},
];
export const cardGrades: { value: Grade; label: string }[] = [
  {value: 0, label: '忘れた'}, {value: 3, label: '難しい'},
  {value: 4, label: '普通'}, {value: 5, label: '簡単'},
];

export function tagsFrom(text: string): string[] {
  return [...new Set(text.split(/[、,\n]/).map(tag => tag.normalize('NFKC').trim()).filter(Boolean))];
}

export function parseSource(text: string): Segment[] {
  const parts: Segment[] = [];
  let start = 0;
  let open = -1;
  let count = 0;
  for (const match of text.matchAll(/[【】]/g)) {
    const index = match.index;
    if (match[0] === '【') {
      if (open >= 0) throw new Error('【】が入れ子になっています。');
      if (index > start) parts.push(text.slice(start, index));
      open = index;
      continue;
    }
    if (open < 0) throw new Error('対応する「【」がありません。');
    const answer = text.slice(open + 1, index);
    if (!answer.trim()) throw new Error('【】に答えを入れてください。');
    parts.push({hole: ++count, answer});
    start = index + 1;
    open = -1;
  }
  if (open >= 0) throw new Error('対応する「】」がありません。');
  if (start < text.length) parts.push(text.slice(start));
  return parts;
}

export const holes = (layout: Segment[]): Hole[] =>
  layout.filter((part): part is Hole => typeof part !== 'string');

export function combinations(n: number): number[][] {
  if (n === 0) return [];
  if (n <= 2) return Array.from({length: n}, (_, i) => [i + 1]);
  if (n === 4) return [[1, 2], [1, 3], [1, 4]];
  const count = n <= 12 ? 3 : n <= 30 ? 4 : 5;
  const width = Math.ceil(n / 2);
  const positions = [
    ...Array.from({length: width}, (_, i) => 2 * i + 1),
    ...Array.from({length: n - width}, (_, i) => 2 * i + 2),
  ];
  const starts: number[] = [];
  for (let i = 0; i < count; i++) {
    const ideal = Math.floor(i * n / count);
    for (let d = 0; d < n; d++) {
      const start = [(ideal - d + n) % n, (ideal + d) % n].find(
        x => !starts.includes(x) && (n % 2 !== 0 || !starts.includes((x + width) % n)),
      );
      if (start !== undefined) {
        starts.push(start);
        break;
      }
    }
  }
  return starts.map(start => Array.from({length: width}, (_, i) => positions[(start + i) % n]));
}

export function generate(text: string, type: string): Variant[] {
  text = text.trim();
  if (!text) throw new Error('原文を入力してください。');
  const parts = parseSource(text);
  if (noBlanks(type)) {
    return [{question: text, answer: '', layout: [text], blank_count: 0}];
  }
  const sets = combinations(holes(parts).length);
  if (sets.length === 0) throw new Error('穴埋め箇所を【】で指定してください。');
  return sets.map(selection => {
    const hidden = new Set(selection);
    const layout = parts.map(part => typeof part === 'string' || hidden.has(part.hole) ? part : part.answer);
    return variantFromLayout(layout);
  });
}

export function variantFromLayout(layout: Segment[]): Variant {
  const answer = holes(layout);
  return {
    layout, blank_count: answer.length,
    question: layout.map(part => typeof part === 'string' ? part : '______').join(''),
    answer: answer.map(part => part.answer).join(' / '),
  };
}

export function layoutFor(card: Card): Segment[] {
  if (card.study_layout) return card.study_layout;
  if (noBlanks(card.card_type)) return [card.question];
  const pieces = card.question.split(/_{3,}/);
  const count = pieces.length - 1;
  const answers = count === 1 ? [card.answer] : card.answer.split(' / ');
  if (count < 1 || answers.length !== count || answers.some(answer => !answer.trim())) {
    return [card.question];
  }
  return pieces.flatMap((text, i) => i === count ? [text] : [text, {hole: i + 1, answer: answers[i]}]);
}

export function matchesVariant(card: Card, variant: Variant, type: string) {
  if (card.card_type !== type || card.question !== variant.question || card.answer !== variant.answer) return false;
  if (!card.study_layout) return holes(layoutFor(card)).length === variant.blank_count;
  return card.study_layout.length === variant.layout.length && card.study_layout.every((part,i) => {
    const other = variant.layout[i];
    return typeof part === 'string' || typeof other === 'string'
      ? part === other
      : part.hole === other.hole && part.answer === other.answer;
  });
}

export function sections(layout: Segment[], size = 8): Segment[][] {
  const result: Segment[][] = [[]];
  let count = 0;
  for (const segment of layout) {
    if (typeof segment !== 'string' && count === size) {
      result.push([]);
      count = 0;
    }
    result[result.length - 1].push(segment);
    if (typeof segment !== 'string') count++;
  }
  return result;
}

export function onlyHoles(layout: Segment[], ids: number[]): Segment[] {
  return layout.map(part => typeof part === 'string' || ids.includes(part.hole) ? part : part.answer);
}

export function difficulty(card: Card): boolean {
  const ease = card.ease_factor ?? 2.5;
  return ease < 2 || (ease < 2.3 && (card.repetitions ?? 0) < 2);
}

export type PracticeItem = {
  id: string; title: string; category: string; cardType: string | null;
  rank: string; layout: Segment[]; answer: string;
};

export function practiceCandidates(library: Library, filters: Filters): PracticeItem[] {
  const sources = new Map(library.sources.map(source => [source.id, source]));
  const targets = new Map(library.targets.map(target => [target.id, target]));
  const latest = new Map<string, Map<number, Grade>>();
  for (const attempt of library.history) {
    if (targets.get(attempt.target_id)?.version !== attempt.version) continue;
    const results = latest.get(attempt.target_id) ?? new Map<number, Grade>();
    for (const item of holes(attempt.layout)) {
      const grade = attempt.grades[item.hole];
      if (!results.has(item.hole) && grade !== undefined) results.set(item.hole, grade);
    }
    latest.set(attempt.target_id, results);
  }
  const picks = new Map<string, { item: PracticeItem; weight: number }>();
  const weakByTarget = new Map<string, Map<number, string>>();
  const includes = (filter: string[], value: string) => filter.length === 0 || filter.includes(value);
  const search = filters.query.trim().toLowerCase();
  for (const card of library.cards) {
    if (card.study_archived_at) continue;
    const source = card.source_id ? sources.get(card.source_id) : undefined;
    const id = card.source_id ?? card.id;
    const category = card.category ?? 'その他';
    const rank = card.rank ?? 'B';
    const topics = source?.study_tags ?? card.study_tags;
    if (!includes(filters.subjects, category) || !includes(filters.ranks, rank) ||
        !includes(filters.types, card.card_type ?? '') ||
        (filters.tags.length && !filters.tags.some(tag => topics.includes(tag))) ||
        (filters.favorite && !card.is_favorite && !source?.study_favorite) ||
        (filters.mode === 'priority' && !ranks.slice(0, 2).includes(rank)) ||
        (search && ![card.title, source?.source_text, card.question, card.answer].some(text => text?.toLowerCase().includes(search)))) {
      continue;
    }
    let layout = layoutFor(card);
    let answer = holes(layout).length ? '' : card.answer;
    let weakCount = 0;
    if (filters.mode === 'weak') {
      const known = latest.get(id);
      if (known?.size) {
        const weak = holes(layout).filter(part => (known.get(part.hole) ?? 4) <= 2);
        if (!weak.length) continue;
        weakCount = weak.length;
        const answers = weakByTarget.get(id) ?? new Map<number, string>();
        for (const hole of weak) {
          const prior = answers.get(hole.hole);
          answers.set(hole.hole, prior !== undefined && prior !== hole.answer ? '' : hole.answer);
        }
        weakByTarget.set(id,answers);
        layout = onlyHoles(layout, weak.map(hole => hole.hole));
        answer = '';
      } else {
        const state = targets.get(id);
        if (!difficulty(state ? {...card, ...state} : card)) continue;
      }
    }
    const weight = weakCount * 5 + ranks.length - ranks.indexOf(rank);
    if ((picks.get(id)?.weight ?? -1) < weight) {
      picks.set(id, {weight, item: {id, title: card.title || '無題', category, rank, cardType: card.card_type, layout, answer}});
    }
  }
  return [...picks.values()].sort((a, b) => b.weight - a.weight).map(({item}) => {
    const weak = weakByTarget.get(item.id);
    const source = sources.get(item.id);
    if (!weak || !source) return item;
    try {
      const original = parseSource(source.source_text);
      const selected = holes(original).filter(hole => weak.get(hole.hole) === hole.answer);
      if (selected.length === weak.size) return {...item,layout:onlyHoles(original,selected.map(hole => hole.hole))};
    } catch {
      // Legacy original: keep the validated question from the selected variant.
    }
    return item;
  });
}

export function shuffle<T>(items: T[]): T[] {
  const result = [...items];
  for (let i = result.length - 1; i > 0; i--) {
    const j = Math.floor(Math.random() * (i + 1));
    [result[i], result[j]] = [result[j], result[i]];
  }
  return result;
}
