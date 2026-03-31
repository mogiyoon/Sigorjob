import AsyncStorage from "@react-native-async-storage/async-storage";

export type MobileLanguage = "ko" | "en";

const LANGUAGE_KEY = "mobile_language";

const messages = {
  ko: {
    app_starting: "Sigorjob 시작 중...",
    app_start_failed: "앱을 시작할 수 없습니다",
    app_start_failed_desc: "초기 설정을 불러오는 중 문제가 발생했습니다.",
    start_manual: "수동 입력으로 시작",
    retry_with_qr: "QR 스캔으로 다시 시도",
    connect_manually: "수동으로 연결하기",
    manual_desc: "PC 앱의 모바일 연결 화면에서 터널 URL과 인증 토큰을 복사해 붙여 넣으세요.",
    tunnel_url: "터널 URL",
    auth_token: "인증 토큰",
    paste_token: "토큰을 붙여 넣으세요",
    saving: "저장 중...",
    connect: "연결하기",
    back_to_qr: "QR 스캔으로 돌아가기",
    connection_failed: "연결 실패",
    invalid_https: "보안 연결(HTTPS) URL만 지원합니다.",
    token_too_short: "토큰 길이가 너무 짧습니다.",
    check_connection_info: "연결 정보를 확인해주세요.",
    qr_camera_permission_needed: "카메라 권한이 필요합니다.",
    camera_preparing: "카메라 준비 중...",
    pair_with_pc: "PC와 연결하기",
    scan_qr_desc: "PC의 Sigorjob 앱에서 표시된 QR 코드를 스캔하세요",
    connecting: "연결 중...",
    invalid_qr: "잘못된 QR 코드입니다.",
    invalid_token: "잘못된 토큰입니다.",
    qr_parse_error: "QR 파싱 오류",
    try_again: "다시 시도",
    reconnect_title: "모바일 연결을 다시 확인해 주세요",
    reconnect_default:
      "모바일 연결이 끊겼습니다. Quick Tunnel 주소가 바뀌었거나 PC 쪽 연결이 다시 열렸을 수 있습니다.",
    reconnect_current: "현재 주소로 다시 연결",
    qr_rescan: "QR 다시 스캔",
    disconnect: "연결 해제",
    manual_reconnect: "수동 입력으로 다시 연결",
    auth_expired: "인증 만료",
    auth_expired_desc: "PC에서 새 QR 코드를 생성하고 다시 스캔해 주세요.",
    confirm: "확인",
    loading_too_long:
      "연결 대기 시간이 너무 길어졌습니다. QR을 다시 스캔하거나 수동으로 새 연결 정보를 입력해 주세요.",
    first_connection_hint: "처음 연결에서는 몇 초 정도 걸릴 수 있습니다.",
    disconnect_title: "연결 해제",
    disconnect_desc: "PC와의 연결을 해제하고 다시 QR 코드를 스캔해야 합니다.",
    cancel: "취소",
    connection_tools: "연결",
    shared_command_received: "공유한 내용을 바로 실행했습니다.",
    shared_command_pending: "PC와 연결되면 공유한 내용을 바로 실행합니다.",
    shared_command_failed: "공유한 내용을 실행하지 못했습니다.",
  },
  en: {
    app_starting: "Starting Sigorjob...",
    app_start_failed: "Unable to start the app",
    app_start_failed_desc: "A problem occurred while loading the initial setup.",
    start_manual: "Start with manual entry",
    retry_with_qr: "Retry with QR scan",
    connect_manually: "Connect manually",
    manual_desc: "Copy the tunnel URL and auth token from the mobile pairing screen on your PC.",
    tunnel_url: "Tunnel URL",
    auth_token: "Auth token",
    paste_token: "Paste the token here",
    saving: "Saving...",
    connect: "Connect",
    back_to_qr: "Back to QR scan",
    connection_failed: "Connection failed",
    invalid_https: "Only secure HTTPS URLs are supported.",
    token_too_short: "The token is too short.",
    check_connection_info: "Please check the connection details.",
    qr_camera_permission_needed: "Camera permission is required.",
    camera_preparing: "Preparing camera...",
    pair_with_pc: "Connect to your PC",
    scan_qr_desc: "Scan the QR code shown in the Sigorjob app on your PC.",
    connecting: "Connecting...",
    invalid_qr: "This QR code is invalid.",
    invalid_token: "This token is invalid.",
    qr_parse_error: "QR parsing error",
    try_again: "Try again",
    reconnect_title: "Please check the mobile connection",
    reconnect_default:
      "The mobile connection was interrupted. The Quick Tunnel address may have changed, or the PC connection may have restarted.",
    reconnect_current: "Reconnect to current address",
    qr_rescan: "Scan QR again",
    disconnect: "Disconnect",
    manual_reconnect: "Reconnect manually",
    auth_expired: "Authentication expired",
    auth_expired_desc: "Generate a new QR code on your PC and scan it again.",
    confirm: "OK",
    loading_too_long:
      "The connection is taking too long. Scan the QR code again or enter a new connection manually.",
    first_connection_hint: "The first connection can take a few seconds.",
    disconnect_title: "Disconnect",
    disconnect_desc: "This will disconnect from your PC and require scanning the QR code again.",
    cancel: "Cancel",
    connection_tools: "Connect",
    shared_command_received: "The shared text was sent for execution.",
    shared_command_pending: "The shared text will run as soon as your PC is connected.",
    shared_command_failed: "Unable to run the shared text.",
  },
} as const;

export type MobileMessageKey = keyof typeof messages.ko;

export async function loadMobileLanguage(): Promise<MobileLanguage> {
  const stored = await AsyncStorage.getItem(LANGUAGE_KEY);
  if (stored === "ko" || stored === "en") return stored;

  const locale = Intl.DateTimeFormat().resolvedOptions().locale?.toLowerCase() ?? "en";
  return locale.startsWith("ko") ? "ko" : "en";
}

export async function saveMobileLanguage(language: MobileLanguage): Promise<void> {
  await AsyncStorage.setItem(LANGUAGE_KEY, language);
}

export function t(language: MobileLanguage, key: MobileMessageKey): string {
  return messages[language][key];
}
