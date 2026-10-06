// 训练视图共享的展示层常量与纯函数。
//
// 抽成独立模块的理由：App.jsx 与各 views/* 组件都要用这些常量，
// 而视图组件不应反向 import App（会形成循环依赖）。

export const COMPLETED_STATES = ['LISTENING_COMPLETED', 'FULLY_COMPLETED']

export const STATE_TEXT = {
  READY_FIRST_LISTEN: '首次盲听',
  FIRST_COMPREHENSION_CHECK: '理解检查',
  DICTATION_PART_1: '听写 Part 1',
  DICTATION_PART_2: '听写 Part 2',
  DICTATION_PART_3: '听写 Part 3',
  SECOND_FULL_LISTEN: '二次复听',
  SECOND_COMPREHENSION_CHECK: '理解复测',
  READING_AVAILABLE: '朗读训练',
  FULL_READING_ASSESSMENT: '全文朗读验收',
  LISTENING_COMPLETED: '听力完成',
  FULLY_COMPLETED: '已完成',
}

export const VIEW_TITLES = {
  home: '训练工作台',
  materials: '素材',
  weekly: '周测 Gate',
  candidates: '候选素材',
  p2: '长期仪表盘',
  training: '训练',
}

export const TRAINING_MODES = [
  { key: 'blind', name: '盲听', desc: '完整播放，不看原文' },
  { key: 'dictation', name: '听写', desc: '逐句精听，逐字校对' },
  { key: 'reading', name: '朗读', desc: '跟读训练与朗读评分' },
  { key: 'weekly', name: '周测', desc: '每周质量闸门与强化' },
]

export function stateText(state) {
  return STATE_TEXT[state] || state || '未开始'
}
