// Shared contract for upload, history, status changes and camera capture results.
export function normalizeCameraResult(result) {
  const log = result.camera_log || result;
  const fusion = result.multimodal || {};
  const environment = {
    temperature: log.temperature_at_capture,
    humidity: log.humidity_at_capture,
    light_level: log.light_at_capture,
  };
  return { ...log,
    final_diagnosis: log.ai_diagnosis ?? log.final_diagnosis,
    final_confidence: log.confidence_score ?? log.final_confidence,
    captured_at: log.timestamp ?? log.captured_at,
    confidence_delta: fusion.confidence_delta,
    sensor_context: Object.values(environment).some(v => v != null) ? environment : null,
  };
}

export async function captureAndWait({ trigger, getResult, onDispatched = () => {},
  isCurrent = () => true, sleep = ms => new Promise(resolve => setTimeout(resolve, ms)),
  now = () => Date.now(), timeoutMs = 90000 }) {
  const command = await trigger();
  if (!command.dispatched) throw new Error(command.message || 'Không gửi được lệnh đến camera.');
  if (!command.capture_id) throw new Error('API chưa hỗ trợ xác nhận đúng lượt chụp. Cần cập nhật API.');
  if (!isCurrent()) return null;
  onDispatched();
  const deadline = now() + timeoutMs;
  while (isCurrent() && now() < deadline) {
    try {
      const result = await getResult(command.capture_id);
      if (!isCurrent()) return null;
      if (result.log_id === command.capture_id) return result;
    } catch (error) {
      if (error.status !== 404) throw error;
    }
    await sleep(2000);
  }
  if (!isCurrent()) return null;
  throw new Error('Chưa nhận được ảnh của lượt chụp này sau 90 giây. Kiểm tra camera, địa chỉ API và firmware; ảnh đến muộn vẫn xuất hiện trong lịch sử.');
}
