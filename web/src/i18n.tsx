import { createContext, useContext, useState, type ReactNode } from "react";

export type Lang = "zh" | "ko";

const dict = {
  appName: { zh: "股票筛选器", ko: "종목 스크리너" },
  login: { zh: "登录", ko: "로그인" },
  logout: { zh: "退出", ko: "로그아웃" },
  username: { zh: "账号", ko: "아이디" },
  password: { zh: "密码", ko: "비밀번호" },
  loginFailed: { zh: "账号或密码错误", ko: "아이디 또는 비밀번호가 올바르지 않습니다" },
  tasks: { zh: "扫描任务", ko: "스캔 작업" },
  history: { zh: "运行记录", ko: "실행 기록" },
  newTask: { zh: "新建任务", ko: "새 작업" },
  editTask: { zh: "编辑任务", ko: "작업 편집" },
  noTasks: { zh: "还没有扫描任务，先新建一个。", ko: "스캔 작업이 없습니다. 새로 만들어 보세요." },
  runNow: { zh: "立即运行", ko: "지금 실행" },
  edit: { zh: "编辑", ko: "편집" },
  delete: { zh: "删除", ko: "삭제" },
  confirmDelete: { zh: "确定删除这个任务？运行记录会保留。", ko: "이 작업을 삭제할까요? 실행 기록은 유지됩니다." },
  save: { zh: "保存", ko: "저장" },
  cancel: { zh: "取消", ko: "취소" },
  saved: { zh: "已保存", ko: "저장됨" },
  name: { zh: "名称", ko: "이름" },
  market: { zh: "市场", ko: "시장" },
  timeframe: { zh: "周期", ko: "주기" },
  universe: { zh: "扫描范围", ko: "스캔 범위" },
  customSymbols: { zh: "自定义列表", ko: "직접 입력" },
  noCommonTimeframe: { zh: "所选市场没有共同支持的周期（加密货币的分钟/小时线不能和股票一起选）", ko: "선택한 시장에 공통으로 지원되는 주기가 없습니다 (암호화폐 분·시간봉은 주식과 함께 선택할 수 없습니다)" },
  timeframeCommonHint: { zh: "只列出所有已选市场都支持的周期", ko: "선택한 모든 시장이 지원하는 주기만 표시합니다" },
  symbolsHint: { zh: "自定义列表：代码用空格或换行分隔；某个市场填写后，该市场只扫描这些代码（优先于扫描范围）", ko: "직접 입력: 종목 코드를 공백 또는 줄바꿈으로 구분합니다. 입력한 시장은 스캔 범위 대신 이 종목만 스캔합니다" },
  exchange: { zh: "交易所", ko: "거래소" },
  schedule: { zh: "定时扫描", ko: "예약 스캔" },
  cron: { zh: "定时表达式", ko: "크론 표현식" },
  cronHint: { zh: "分 时 日 月 周；留空为仅手动运行", ko: "분 시 일 월 요일; 비워 두면 수동 실행만" },
  timezone: { zh: "时区", ko: "시간대" },
  useDefault: { zh: "用建议值", ko: "권장값 사용" },
  enabled: { zh: "启用定时", ko: "예약 사용" },
  notify: { zh: "KakaoTalk 通知", ko: "카카오톡 알림" },
  nextRun: { zh: "下次运行", ko: "다음 실행" },
  lastRun: { zh: "上次运行", ko: "최근 실행" },
  manualOnly: { zh: "仅手动", ko: "수동만" },
  conditions: { zh: "筛选条件", ko: "스크리닝 조건" },
  combine: { zh: "组合方式", ko: "조합 방식" },
  logicAnd: { zh: "全部满足（AND）", ko: "모두 충족 (AND)" },
  logicOr: { zh: "任一满足（OR）", ko: "하나 이상 충족 (OR)" },
  direction: { zh: "方向", ko: "방향" },
  both: { zh: "顶部和底部", ko: "천장·바닥 모두" },
  bottom: { zh: "底部（看涨）", ko: "바닥 (상승)" },
  top: { zh: "顶部（看跌）", ko: "천장 (하락)" },
  fractal: { zh: "顶底分型", ko: "천장·바닥 분형" },
  divergence: { zh: "RSI 背离", ko: "RSI 다이버전스" },
  filters: { zh: "过滤", ko: "필터" },
  on: { zh: "开启", ko: "사용" },
  inclusion: { zh: "包含关系处理", ko: "포함 관계 처리" },
  strictBi: { zh: "严格笔规则", ko: "엄격한 필(笔) 규칙" },
  recentBars: { zh: "时效（最近 N 根）", ko: "유효 기간 (최근 N봉)" },
  minStrength: { zh: "最低强度", ko: "최소 강도" },
  any: { zh: "不限", ko: "제한 없음" },
  confirmK4: { zh: "第四根确认", ko: "4번째 봉 확인" },
  volumeCheck: { zh: "成交量条件", ko: "거래량 조건" },
  volumeMa: { zh: "均量天数", ko: "평균 거래량 기간" },
  rsiPeriod: { zh: "RSI 周期", ko: "RSI 기간" },
  regular: { zh: "常规背离", ko: "일반 다이버전스" },
  hidden: { zh: "隐藏背离", ko: "히든 다이버전스" },
  minGap: { zh: "最小间隔", ko: "최소 간격" },
  maxGap: { zh: "最大间隔", ko: "최대 간격" },
  oversold: { zh: "超卖线", ko: "과매도 기준" },
  overbought: { zh: "超买线", ko: "과매수 기준" },
  emptyOff: { zh: "留空为关闭", ko: "비우면 사용 안 함" },
  minFractalStrength: { zh: "第二个分型最低强度", ko: "두 번째 분형 최소 강도" },
  minPriceChange: { zh: "最小价格差 %", ko: "최소 가격 차이 %" },
  minRsiDiff: { zh: "最小 RSI 差", ko: "최소 RSI 차이" },
  scoreWeights: { zh: "强度分权重（RSI / 价格）", ko: "강도 점수 가중치 (RSI / 가격)" },
  excludeSt: { zh: "剔除 ST", ko: "ST 종목 제외" },
  excludeEtf: { zh: "剔除 ETF / SPAC", ko: "ETF / 스팩 제외" },
  excludeTokenized: { zh: "剔除代币化股票 / 黄金代币", ko: "토큰화 주식 / 금 토큰 제외" },
  minListDays: { zh: "上市至少天数", ko: "최소 상장 일수" },
  minMarketCap: { zh: "最低市值（当地货币）", ko: "최소 시가총액 (현지 통화)" },
  strong: { zh: "强", ko: "강" },
  medium: { zh: "中", ko: "중" },
  weak: { zh: "弱", ko: "약" },
  regularShort: { zh: "常规", ko: "일반" },
  hiddenShort: { zh: "隐藏", ko: "히든" },
  status_queued: { zh: "排队中", ko: "대기 중" },
  status_running: { zh: "运行中", ko: "실행 중" },
  status_done: { zh: "完成", ko: "완료" },
  status_failed: { zh: "失败", ko: "실패" },
  trigger_manual: { zh: "手动", ko: "수동" },
  trigger_schedule: { zh: "定时", ko: "예약" },
  results: { zh: "结果", ko: "결과" },
  noResults: { zh: "没有符合条件的标的", ko: "조건에 맞는 종목이 없습니다" },
  symbol: { zh: "代码", ko: "코드" },
  side: { zh: "方向", ko: "방향" },
  date: { zh: "时间", ko: "시간" },
  close: { zh: "收盘价", ko: "종가" },
  strength: { zh: "分型强度", ko: "분형 강도" },
  divType: { zh: "背离", ko: "다이버전스" },
  score: { zh: "强度分", ko: "강도 점수" },
  priceChange: { zh: "价格差 %", ko: "가격 차이 %" },
  rsiDiff: { zh: "RSI 差", ko: "RSI 차이" },
  downloadCsv: { zh: "下载 CSV", ko: "CSV 다운로드" },
  failedSymbols: { zh: "未取到数据的标的", ko: "데이터를 가져오지 못한 종목" },
  scanned: { zh: "已扫描", ko: "스캔 완료" },
  chartHint: { zh: "点击表格中的一行查看 K 线图", ko: "표의 행을 클릭하면 차트를 볼 수 있습니다" },
  loading: { zh: "加载中…", ko: "불러오는 중…" },
  back: { zh: "返回", ko: "뒤로" },
  task: { zh: "任务", ko: "작업" },
  time: { zh: "时间", ko: "시간" },
  status: { zh: "状态", ko: "상태" },
  view: { zh: "查看", ko: "보기" },
  progress: { zh: "进度", ko: "진행" },
  settings: { zh: "设置", ko: "설정" },
  kakao: { zh: "KakaoTalk 通知", ko: "카카오톡 알림" },
  kakaoNotConfigured: { zh: "服务器尚未设置 KAKAO_REST_API_KEY。请在 Kakao Developers 创建应用后，把 REST API 키写进服务器的 .env 并重启。", ko: "서버에 KAKAO_REST_API_KEY가 설정되지 않았습니다. Kakao Developers에서 앱을 만든 뒤 REST API 키를 서버 .env에 넣고 재시작하세요." },
  kakaoRedirect: { zh: "在 Kakao Developers 中登记的 Redirect URI", ko: "Kakao Developers에 등록할 Redirect URI" },
  kakaoConnected: { zh: "已连接", ko: "연결됨" },
  kakaoNotConnected: { zh: "未连接", ko: "연결 안 됨" },
  kakaoConnect: { zh: "连接 KakaoTalk", ko: "카카오톡 연결" },
  kakaoReconnect: { zh: "重新连接", ko: "다시 연결" },
  kakaoTest: { zh: "发送测试消息", ko: "테스트 메시지 보내기" },
  kakaoTestSent: { zh: "已发送，请查看 KakaoTalk「나와의 채팅」", ko: "전송했습니다. 카카오톡 '나와의 채팅'을 확인하세요" },
  kakaoDisconnect: { zh: "断开", ko: "연결 해제" },
  kakaoRefreshExpires: { zh: "授权有效期至（定时任务运行时会自动续期）", ko: "인증 만료일 (예약 작업이 실행되면 자동 연장)" },
  kakaoError: { zh: "连接失败", ko: "연결 실패" },
  kakaoLang: { zh: "消息语言（NOTIFY_LANG）", ko: "메시지 언어 (NOTIFY_LANG)" },
  kakaoSetupTitle: { zh: "Kakao Developers 应用设置清单", ko: "Kakao Developers 앱 설정 체크리스트" },
  kakaoStep1: { zh: "앱 키 → 复制 REST API 키 到服务器 .env 的 KAKAO_REST_API_KEY", ko: "앱 키 → REST API 키를 서버 .env의 KAKAO_REST_API_KEY에 입력" },
  kakaoStep2: { zh: "카카오 로그인 → 활성화 설정 ON", ko: "카카오 로그인 → 활성화 설정 ON" },
  kakaoStep3: { zh: "카카오 로그인 → Redirect URI 登记下面这个地址（必须完全一致）", ko: "카카오 로그인 → Redirect URI에 아래 주소를 등록 (정확히 일치해야 함)" },
  kakaoStep4: { zh: "동의항목 → 「카카오톡 메시지 전송（talk_message）」设为「선택 동의」并保存。没设置会出现 KOE205", ko: "동의항목 → '카카오톡 메시지 전송 (talk_message)'을 '선택 동의'로 설정 후 저장. 설정하지 않으면 KOE205 오류" },
  kakaoStep5: { zh: "플랫폼 → Web 사이트 도메인 登记网站地址（消息里的链接要用到）", ko: "플랫폼 → Web 사이트 도메인에 사이트 주소 등록 (메시지 링크에 필요)" },
  kakaoStep6: { zh: "보안 → 若启用了 Client Secret，填到 .env 的 KAKAO_CLIENT_SECRET", ko: "보안 → Client Secret을 사용하면 .env의 KAKAO_CLIENT_SECRET에 입력" },
  kakaoErrors: { zh: "常见错误：KOE205 = 第 4 步未设置；KOE006 = Redirect URI 未登记或不一致；KOE101 = REST API 키 错误", ko: "자주 나오는 오류: KOE205 = 4단계 미설정, KOE006 = Redirect URI 미등록 또는 불일치, KOE101 = REST API 키 오류" },
  kakaoConsentNote: { zh: "授权时请勾选「카카오톡 메시지 전송」，否则无法发送消息", ko: "동의 화면에서 '카카오톡 메시지 전송'에 꼭 체크하세요. 체크하지 않으면 메시지를 보낼 수 없습니다" },
  legendFractal: { zh: "▲▼ 分型（强 / 中 / 弱 颜色由深到浅）", ko: "▲▼ 분형 (강 / 중 / 약 순으로 진한 색)" },
  legendDiv: { zh: "虚线：背离", ko: "점선: 다이버전스" },
} as const;

export type Key = keyof typeof dict;

const Ctx = createContext<{ lang: Lang; setLang: (l: Lang) => void; t: (k: Key) => string }>(null!);

function initialLang(): Lang {
  try {
    const saved = localStorage.getItem("lang");
    if (saved === "zh" || saved === "ko") return saved;
  } catch { /* ignore */ }
  return navigator.language.startsWith("ko") ? "ko" : "zh";
}

export function I18nProvider({ children }: { children: ReactNode }) {
  const [lang, setLangState] = useState<Lang>(() => {
    const l = initialLang();
    document.documentElement.lang = l;
    return l;
  });
  const setLang = (l: Lang) => {
    setLangState(l);
    document.documentElement.lang = l;
    try { localStorage.setItem("lang", l); } catch { /* ignore */ }
  };
  const t = (k: Key) => dict[k][lang];
  return <Ctx.Provider value={{ lang, setLang, t }}>{children}</Ctx.Provider>;
}

export const useI18n = () => useContext(Ctx);

export const MARKET_NAMES: Record<string, Record<Lang, string>> = {
  crypto: { zh: "加密货币", ko: "암호화폐" },
  kr: { zh: "韩国股市", ko: "한국 주식" },
  cn: { zh: "A 股", ko: "중국 A주" },
  us: { zh: "美股", ko: "미국 주식" },
  hk: { zh: "港股", ko: "홍콩 주식" },
};

export const UNIVERSE_NAMES: Record<string, Record<Lang, string>> = {
  all: { zh: "全市场", ko: "전체 시장" },
  top50: { zh: "成交额前 50", ko: "거래대금 상위 50" },
  top100: { zh: "成交额前 100", ko: "거래대금 상위 100" },
  top200: { zh: "成交额前 200", ko: "거래대금 상위 200" },
  kospi: { zh: "KOSPI", ko: "코스피" },
  kosdaq: { zh: "KOSDAQ", ko: "코스닥" },
  kospi200: { zh: "KOSPI 200", ko: "코스피 200" },
  kosdaq150: { zh: "KOSDAQ 150", ko: "코스닥 150" },
  csi300: { zh: "沪深 300", ko: "CSI 300" },
  csi500: { zh: "中证 500", ko: "CSI 500" },
  csi1000: { zh: "中证 1000", ko: "CSI 1000" },
  sse50: { zh: "上证 50", ko: "SSE 50" },
  sp500: { zh: "S&P 500", ko: "S&P 500" },
  hsi: { zh: "恒生指数", ko: "항셍지수" },
};
