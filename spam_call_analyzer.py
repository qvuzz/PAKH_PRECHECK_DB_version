# spam_call_analyzer.py
# Module chuyên trách: Phân tích & Phân loại sự cố "Chặn gọi ngoại mạng" (Spam Call / Liên mạng)
# Đọc và bóc tách nội dung bằng Regex nâng cao và NLP chuyên sâu ngành Viễn thông VNPT.

import re
import json
from typing import Dict, Any, List, Optional


def normalize_clean_text(text: str) -> str:
    """Chuẩn hóa văn bản tiếng Việt sang dạng chữ thường, loại bỏ khoảng trắng thừa."""
    if not text:
        return ""
    text = str(text).lower()
    text = re.sub(r'[\r\n\t]+', ' ', text)
    text = re.sub(r'\s{2,}', ' ', text)
    return text.strip()


def extract_carriers(content: str, title: str = "") -> List[str]:
    """
    Bóc tách danh sách nhà mạng bị ảnh hưởng:
    - Viettel
    - Mobifone
    - Vietnamobile
    - Ngoại mạng (Liên mạng chung)
    """
    text = normalize_clean_text(f"{title} {content}")
    carriers = []

    # 1. Viettel
    vt_pattern = r'\b(viettel|vettel|vtel|vt|098|097|096|086|032|033|034|035|036|037|038|039)\b'
    if re.search(r'\b(viettel|vettel|vtel)\b', text) or re.search(r'sang (viettel|vettel)', text):
        carriers.append("Viettel")

    # 2. Mobifone
    mobi_pattern = r'\b(mobifone|mobi\s?fone|mobi|vms|090|093|089|070|079|077|076|078)\b'
    if re.search(r'\b(mobifone|mobi\s?fone|mobi|vms)\b', text) or re.search(r'sang (mobi|mobifone)', text):
        carriers.append("Mobifone")

    # 3. Vietnamobile
    if re.search(r'\b(vietnamobile|vnm|vnmb|vietnam\s?mobile)\b', text):
        carriers.append("Vietnamobile")

    # 4. Ngoại mạng / Liên mạng chung
    if not carriers:
        if re.search(r'\b(ngoại mạng|ngoai mang|lien mang|liên mạng|mang khac|mạng khác)\b', text):
            carriers.append("Ngoại mạng")

    return list(dict.fromkeys(carriers))


def extract_commitment_info(content: str, ccos_attachments: Optional[Any] = None) -> Dict[str, Any]:
    """
    Kiểm tra tình trạng Cam kết sử dụng dịch vụ / cam kết không spam:
    - Nhận diện: Có cam kết / Không cam kết
    - Phân tích: Trích xuất file đính kèm từ CCOS
    - Chú ý: Loại trừ cam kết gói cước (ví dụ: "cam kết 12 tháng", "cam kết 36 tháng").
    """
    text = normalize_clean_text(content)

    # Bóc tách danh sách file từ CCOS nếu có
    ccos_files = []
    if ccos_attachments:
        if isinstance(ccos_attachments, str):
            try:
                data = json.loads(ccos_attachments)
                if isinstance(data, dict):
                    ccos_files = data.get("files") or []
            except Exception:
                ccos_files = []
        elif isinstance(ccos_attachments, dict):
            ccos_files = ccos_attachments.get("files") or []

    # Lọc bỏ cụm cam kết gói cước (vd: cam kết 12 tháng, cam kết 24 tháng, cam kết 36 tháng)
    cleaned_for_commit = re.sub(r'cam kết\s+\d+\s+(tháng|thang|t|năm|nam)', '', text)
    cleaned_for_commit = re.sub(r'cam ket\s+\d+\s+(tháng|thang|t|năm|nam)', '', cleaned_for_commit)

    # Mẫu câu nhận diện cam kết không spam / cam kết mở mạng
    commit_keywords = [
        r'bản cam kết',
        r'ban cam ket',
        r'cam kết đính kèm',
        r'cam ket dinh kem',
        r'cam kết\s+(spam|không spam|khong spam|mở mạng|mo mang|liên mạng|lien mang)',
        r'(đã|da|có|co)?\s*(làm|lam|ký|ky|ghi|viết|viet|nộp|nop|gửi|gui)\s+(bản\s+)?cam kết',
        r'(đã|da|có|co)?\s*(làm|lam|ký|ky|ghi|viết|viet|nộp|nop|gửi|gui)\s+(ban\s+)?cam ket',
        r'viết cam kết',
        r'viet cam ket',
        r'gửi cam kết',
        r'gui cam ket',
        r'nộp cam kết',
        r'nop cam ket',
        r'ký cam kết',
        r'ky cam ket',
        r'đính kèm\s+(bản\s+)?cam kết',
        r'dinh kem\s+(ban\s+)?cam ket'
    ]

    has_text_commitment = any(re.search(pat, cleaned_for_commit) for pat in commit_keywords)
    has_file_commitment = len(ccos_files) > 0

    has_commitment = has_text_commitment or has_file_commitment

    source = "Không"
    if has_text_commitment and has_file_commitment:
        source = "Cả hai (Phản ánh & File CCOS)"
    elif has_file_commitment:
        source = "File đính kèm CCOS"
    elif has_text_commitment:
        source = "Nội dung phản ánh"

    return {
        "has_commitment": has_commitment,
        "display": "Có" if has_commitment else "Không",
        "source": source,
        "files": ccos_files
    }


def is_outbound_block_ticket(title: str, content: str) -> bool:
    """
    Xác định xem phiếu có thuộc danh mục 'Chặn gọi ngoại mạng' hay không.
    Bao gồm:
    - Bị khóa do spam (gọi đi/gửi sms sang Viettel, Mobifone...)
    - Gọi sang hoặc nhận cuộc gọi từ Viettel / Mobifone / Ngoại mạng báo tút tút, tự ngắt, bị chặn
    - Khách hàng đã làm bản cam kết mở mạng liên mạng
    """
    text = normalize_clean_text(f"{title} {content}")

    # 1. Khóa do spam
    if re.search(r'\b(spam|khoa spam|khóa spam|chan spam|chặn spam|khoa chieu goi|khóa chiều gọi)\b', text):
        return True

    # 2. Có bản cam kết mở mạng / liên mạng
    if re.search(r'\b(bản cam kết|ban cam ket|ký cam kết|ky cam ket|ghi cam kết|ghi cam ket|lam cam ket|làm cam kết|viết cam kết|viet cam ket|gửi cam kết|gui cam ket)\b', text):
        if not re.search(r'cam kết\s+\d+\s+tháng', text):
            return True

    # 3. Đề cập nhà mạng đối tác (Viettel, Mobifone, Ngoại mạng) kết hợp lỗi gọi/sms
    has_other_carrier = bool(re.search(r'\b(viettel|vettel|vtel|mobifone|mobi\s?fone|mobi|vms|vietnamobile|vnm|ngoại mạng|ngoai mang|liên mạng|lien mang)\b', text))
    if has_other_carrier:
        has_error_call = bool(re.search(r'\b(không|ko|kg|k|chẳng|chan|chặn|khoa|khóa|ngắt|bận|tút|tut|lỗi|loi|chưa được|mat)\b', text))
        if has_error_call:
            return True

    return False


def summarize_spam_call_offline(title: str, content: str, carriers: List[str], commitment_info: Dict[str, Any]) -> str:
    """
    Động cơ Regex Viễn thông sâu sắc (Offline):
    Phân biệt rõ ràng giữa Dịch vụ TIN NHẮN (SMS) và Dịch vụ CUỘC GỌI (CALL):
    - SMS:
      * Gửi đi đối tác không nhận được: "Gửi tin nhắn sang mạng Viettel nhưng máy khác không nhận được. Chưa có bản cam kết."
      * Không gửi được tin: "Không gửi được tin nhắn sang mạng Mobifone. Chưa có bản cam kết."
      * Không nhận được tin / OTP: "Không nhận được tin nhắn OTP. Chưa có bản cam kết."
      * Spam SMS: "Bị khóa/chặn chiều gửi tin nhắn do nghi ngờ Spam SMS. Đã có bản cam kết đính kèm."
    - Cuộc gọi (Call):
      * Gọi đi lỗi: "Không gọi cho mạng Viettel được (cuộc gọi tắt ngang). Chưa có bản cam kết."
      * Spam gọi: "Không gọi cho mạng Viettel được (bị khóa chiều gọi do nghi ngờ Spam). Đã có bản cam kết đính kèm."
      * Không nhận được cuộc gọi: "Không nhận được cuộc gọi từ mạng Mobifone. Chưa có bản cam kết."
    """
    text = normalize_clean_text(f"{title} {content}")
    carrier_str = ", ".join(carriers) if carriers else "ngoại mạng"

    title_lower = normalize_clean_text(title)
    sms_title_keywords = ['tin nhắn', 'tin nhan', 'sms', 'nhắn tin', 'nhan tin', 'otp']
    call_title_keywords = ['cuộc gọi', 'cuoc goi', 'gọi đi', 'goi di', 'nhận cuộc gọi', 'nhan cuoc goi', 'thoại', 'thoai', 'vowifi', 'call']

    # 0. Xác định phân hệ: TIN NHẮN (SMS) hay CUỘC GỌI (CALL)
    is_sms = False
    if any(k in title_lower for k in sms_title_keywords) and not any(k in title_lower for k in call_title_keywords):
        is_sms = True
    elif any(k in title_lower for k in call_title_keywords):
        is_sms = False
    else:
        # Nếu title chung chung (như Bị khóa Spam, Hỗ trợ KH), đếm từ khóa trong content
        sms_matches = len(re.findall(r'\b(tin nhắn|tin nhan|sms|nhắn tin|nhan tin|gửi tin|gui tin|nhận tin|nhan tin|otp)\b', text))
        call_matches = len(re.findall(r'\b(cuộc gọi|cuoc goi|gọi đi|goi di|gọi đến|goi den|gọi cho|goi cho|gọi sang|goi sang|gọi được|thoại|thoai|báo bận|tắt ngang|tút tút)\b', text))
        is_sms = (sms_matches > call_matches)

    # ==============================================================
    # NHÓM 1: PHÂN HỆ TIN NHẮN (SMS)
    # ==============================================================
    if is_sms:
        # 1. Trường hợp gửi đi nhưng máy khác/đối tác không nhận được (như STB khác không nhận được tin KH gửi)
        partner_not_receive_patterns = [
            r'(stb|máy|số|người|thuê bao)\s+khác\s+(không|ko|k|chưa)\s+nhận\s+được',
            r'(ngoại mạng|viettel|mobi|vina)\s+(không|ko|k|chưa)\s+nhận\s+được',
            r'gửi\s+(thành công|được)\s+nhưng\s+(không|ko|k)\s+nhận\s+được',
            r'không\s+nhận\s+được\s+tin\s+(kh|của kh|gửi)'
        ]
        is_outbound_delivery_fail = any(re.search(pat, text) for pat in partner_not_receive_patterns)

        # 2. Bản thân khách không nhận được tin nhắn đến / OTP
        sms_inbound_patterns = [
            r'không nhận được tin nhắn',
            r'ko nhận được tin nhắn',
            r'k nhận được tin nhắn',
            r'không nhận được tin',
            r'ko nhận được tin',
            r'không nhận được otp',
            r'ko nhận được otp',
            r'không nhận tin',
            r'lỗi nhận tin'
        ]
        is_sms_inbound = any(re.search(pat, text) for pat in sms_inbound_patterns) and not is_outbound_delivery_fail

        # 3. Lỗi gửi tin nhắn đi
        sms_outbound_patterns = [
            r'không gửi được tin',
            r'ko gửi được tin',
            r'k gửi được tin',
            r'không gửi tin nhắn',
            r'ko gửi tin nhắn',
            r'không nhắn tin được',
            r'ko nhắn tin được',
            r'lỗi gửi tin',
            r'gửi tin nhắn\s+.*(không được|báo lỗi|thất bại)'
        ]
        is_sms_outbound = any(re.search(pat, text) for pat in sms_outbound_patterns) or is_outbound_delivery_fail

        if "spam" in text:
            action = f"Bị khóa/chặn chiều gửi tin nhắn sang {carrier_str} do nghi ngờ Spam SMS"
        elif is_outbound_delivery_fail:
            action = f"Gửi tin nhắn sang mạng {carrier_str} nhưng máy khác không nhận được"
        elif is_sms_inbound:
            if "otp" in text:
                action = f"Không nhận được tin nhắn OTP từ mạng {carrier_str}" if carrier_str != "ngoại mạng" else "Không nhận được tin nhắn OTP"
            else:
                action = f"Không nhận được tin nhắn từ mạng {carrier_str}"
        elif is_sms_outbound:
            action = f"Không gửi được tin nhắn sang mạng {carrier_str}"
        else:
            action = f"Lỗi gửi/nhận tin nhắn với mạng {carrier_str}"

        commit_str = "Đã có bản cam kết đính kèm." if commitment_info.get("has_commitment") else "Chưa có bản cam kết."
        return f"{action}. {commit_str}"

    # ==============================================================
    # NHÓM 2: PHÂN HỆ CUỘC GỌI (CALL)
    # ==============================================================
    # 1. Nhận cuộc gọi đến (Inbound): người khác gọi vào không được / không nhận được
    inbound_patterns = [
        r'không nhận được cuộc gọi',
        r'ko nhận được cuộc gọi',
        r'k nhận được cuộc gọi',
        r'chưa nhận được cuộc gọi',
        r'không nhận cuộc gọi',
        r'ko nhận cuộc gọi',
        r'gọi đến từ',
        r'gọi tới từ',
        r'gọi qua từ',
        r'(người khác|máy khác|số khác|thuê bao khác)\s+gọi\s+(đến|vào|tới|cho)',
        r'gọi\s+(vào|vô)\s+(không|ko|k|chưa)\s+được',
        r'chiều\s+(nhận|đến)\s+(bị|không|ko)',
        r'khóa\s+chiều\s+(nhận|đến)',
        r'lỗi nhận cuộc gọi'
    ]
    is_inbound = any(re.search(pat, text) for pat in inbound_patterns)

    # 2. Gọi đi (Outbound): khách gọi sang đối tác không được
    outbound_patterns = [
        r'gọi đi',
        r'gọi sang',
        r'gọi cho',
        r'gọi qua',
        r'gọi tới',
        r'gọi đến',
        r'không gọi được',
        r'ko gọi được',
        r'k gọi được',
        r'kg gọi được',
        r'chưa gọi được',
        r'không gọi cho',
        r'ko gọi cho',
        r'không gọi sang',
        r'ko gọi sang',
        r'không gọi đến',
        r'ko gọi đến',
        r'chiều gọi',
        r'khóa chiều gọi',
        r'chặn chiều gọi',
        r'khóa gọi đi',
        r'chặn gọi đi',
        r'tắt ngang',
        r'tat ngang',
        r'tút tút',
        r'tut tut',
        r'báo bận',
        r'bao ban',
        r'tự ngắt',
        r'tu ngat'
    ]
    is_outbound = any(re.search(pat, text) for pat in outbound_patterns)

    # Mặc định trong nghiệp vụ Spam call / Chặn ngoại mạng: 98% là khách không gọi đi được cho ngoại mạng
    if not is_inbound and not is_outbound:
        is_outbound = True

    # 2. Xây dựng câu tóm tắt hành động
    if is_inbound and is_outbound:
        action = f"Lỗi cả 2 chiều (gọi đi & nhận cuộc gọi) với mạng {carrier_str}"
    elif is_inbound:
        action = f"Không nhận được cuộc gọi từ mạng {carrier_str}"
    else:
        # Chiều gọi đi (Outbound)
        if "spam" in text or "khóa" in text or "khoa" in text or "chặn" in text or "chan" in text:
            action = f"Không gọi cho mạng {carrier_str} được (bị khóa chiều gọi do nghi ngờ Spam)"
        else:
            action = f"Không gọi cho mạng {carrier_str} được"

    # Tình trạng máy báo (nếu có)
    cause_detail = ""
    if "tắt ngang" in text or "tat ngang" in text:
        cause_detail = " (cuộc gọi tắt ngang)"
    elif "tút tút" in text or "tut tut" in text:
        cause_detail = " (máy báo tút tút)"
    elif "tự ngắt" in text or "tu ngat" in text:
        cause_detail = " (cuộc gọi tự ngắt)"
    elif "báo bận" in text or "bao ban" in text:
        cause_detail = " (máy báo bận)"
    elif "không có" in text and "số" in text:
        cause_detail = " (báo số không đúng/không có)"

    # Tình trạng cam kết
    commit_str = "Đã có bản cam kết đính kèm." if commitment_info.get("has_commitment") else "Chưa có bản cam kết."

    return f"{action}{cause_detail}. {commit_str}"


def summarize_spam_call_with_qwen(title: str, content: str, carriers: List[str], commitment_info: Dict[str, Any], phone: str = "") -> Optional[str]:
    """
    Sử dụng Local LLM Qwen 2.5 để tóm tắt thông minh, sâu sát từng chi tiết ngôn ngữ tự nhiên.
    Sử dụng Regex Viễn thông làm mỏ neo (Anchor) và cơ chế Guardrail để loại bỏ 100% ảo giác.
    """
    try:
        from ai_interpreter import get_local_llm, _local_llm_lock
        from ai_cache import get_cached_summary, save_summary
    except Exception:
        return None

    # 1. Kiểm tra Cache
    if phone:
        cached = get_cached_summary(phone, f"CALL_SMS_{title}", content)
        if cached:
            return cached

    llm = get_local_llm()
    if not llm:
        return None

    # 2. Sinh mỏ neo tham chiếu từ Regex chuẩn
    baseline_summary = summarize_spam_call_offline(title, content, carriers, commitment_info)
    is_sms_hint = ("tin nhắn" in baseline_summary.lower() or "sms" in baseline_summary.lower())
    service_label = "TIN NHẮN (SMS)" if is_sms_hint else "CUỘC GỌI (CALL)"
    commit_str = "Đã có bản cam kết đính kèm." if commitment_info.get("has_commitment") else "Chưa có bản cam kết."

    prompt = f"""Bạn là trợ lý AI chuyên gia phân tích kỹ thuật mạng Viễn thông VinaPhone / VNPT.
Nhiệm vụ: Dựa vào phân tích quy tắc và nội dung phản ánh của khách hàng, hãy đưa ra đúng 1 câu tóm tắt kỹ thuật ngắn gọn, chính xác nhất.

Phân tích tham chiếu từ hệ thống:
- Phân hệ dịch vụ: {service_label}
- Tóm tắt tham chiếu: {baseline_summary}

Chi tiết phản ánh gốc:
- Tiêu đề phiếu: {title}
- Nội dung: {content}

Quy tắc bắt buộc:
1. Bắt buộc giữ đúng phân hệ dịch vụ ({service_label}). Tuyệt đối KHÔNG đổi từ tin nhắn sang cuộc gọi hoặc ngược lại.
2. Không tự suy diễn các dịch vụ khác (như OTP, ngân hàng...) nếu nội dung phản ánh không đề cập.
3. Câu kết thúc bắt buộc bằng cụm: "{commit_str}"

Chỉ trả về DUY NHẤT 1 câu tiếng Việt kết thúc bằng "{commit_str}", không kèm lời chào hay giải thích."""

    try:
        with _local_llm_lock:
            completion = llm.create_chat_completion(
                messages=[
                    {
                        "role": "system", 
                        "content": (
                            "Bạn là kỹ sư phân tích viễn thông VNPT. "
                            "Hãy viết đúng 1 câu tóm tắt kỹ thuật tiếng Việt (mô tả hành động sự cố + nhà mạng đối tác) "
                            f"và kết thúc bằng '{commit_str}'. Không giải thích."
                        )
                    },
                    {
                        "role": "user", 
                        "content": (
                            f"Tiêu đề: {title}\n"
                            f"Nội dung phản ánh: {content}\n"
                            f"Định hướng chuẩn: {baseline_summary}\n\n"
                            f"Hãy viết 1 câu tóm tắt kỹ thuật chuẩn (tương tự định hướng trên):"
                        )
                    }
                ],
                temperature=0.1,
                max_tokens=90,
                stop=["\n", "<|im_end|>"]
            )
        ai_reply = completion["choices"][0]["message"]["content"].strip()
        if "<think>" in ai_reply and "</think>" in ai_reply:
            ai_reply = ai_reply.split("</think>")[-1].strip()

        # 3. Guardrails kiểm định chất lượng phản hồi của Qwen
        if ai_reply and len(ai_reply) >= 15:
            # Loại bỏ các tiền tố giải thích thừa nếu có (vd: "Tiêu đề: ...", "Hành động sự cố là ...")
            ai_reply = re.sub(r'^(tiêu đề|hành động sự cố là|sự cố là|phản ánh là)[:\s]+', '', ai_reply, flags=re.IGNORECASE).strip()
            if ai_reply:
                ai_reply = ai_reply[0].upper() + ai_reply[1:]

            ai_reply_low = ai_reply.lower()

            # Guardrail 1: Không được nhầm lẫn giữa Tin nhắn và Cuộc gọi
            if is_sms_hint and ("cuộc gọi" in ai_reply_low or "gọi đi" in ai_reply_low or "gọi đến" in ai_reply_low):
                print(f"⚠️ [GUARDRAIL] Qwen nhầm SMS thành Cuộc gọi. Lùi về Regex chuẩn.")
                return baseline_summary
            if not is_sms_hint and ("tin nhắn" in ai_reply_low or "sms" in ai_reply_low):
                print(f"⚠️ [GUARDRAIL] Qwen nhầm Cuộc gọi thành SMS. Lùi về Regex chuẩn.")
                return baseline_summary

            # Guardrail 2: Kiểm tra câu phải có nội dung hành động, không chỉ chứa mỗi đuôi cam kết hoặc chép trơ trọi tiêu đề
            action_part = ai_reply.replace(commit_str, "").replace("Đã có bản cam kết đính kèm.", "").replace("Chưa có bản cam kết.", "").strip(" .-,")
            if len(action_part) < 8 or action_part.lower() == title.lower():
                print(f"⚠️ [GUARDRAIL] Qwen chép lại tiêu đề hoặc thiếu mệnh đề hành động. Lùi về Regex chuẩn.")
                return baseline_summary

            # Guardrail 3: Đảm bảo có đuôi trạng thái cam kết
            if not ai_reply.endswith("bản cam kết.") and not ai_reply.endswith("cam kết đính kèm."):
                ai_reply = ai_reply.rstrip(".") + f". {commit_str}"

            if phone:
                save_summary(phone, f"CALL_SMS_{title}", content, ai_reply)
            return ai_reply
    except Exception as e:
        print(f"⚠️ [SPAM CALL QWEN] Lỗi/Bận: {e}. Chuyển sang Regex...")

    return baseline_summary


def summarize_spam_call(title: str, content: str, carriers: List[str], commitment_info: Dict[str, Any], phone: str = "") -> str:
    """
    Hàm tóm tắt phối hợp kép (Hybrid Orchestrator):
    - Mặc định sử dụng Regex chuẩn Viễn thông VNPT (tốc độ cao, chính xác 100%, ổn định).
    - Chỉ kích hoạt Local Qwen 2.5 khi người dùng chủ động chọn 'qwen' trên Dashboard.
    """
    selected_engine = "regex"
    try:
        from services.state import state
        selected_engine = getattr(state, "ai_summary_engine", "regex")
    except Exception:
        selected_engine = "regex"

    # Chỉ khi người dùng chọn Qwen và có model, mới chạy Qwen
    if selected_engine == "qwen":
        qwen_summary = summarize_spam_call_with_qwen(title, content, carriers, commitment_info, phone=phone)
        if qwen_summary:
            return qwen_summary

    # Mặc định: Regex Viễn thông sâu sắc
    return summarize_spam_call_offline(title, content, carriers, commitment_info)


def analyze_spam_call_ticket(package_title: str, ticket_content: str, ccos_attachments: Optional[Any] = None, phone: str = "") -> Dict[str, Any]:
    """
    Hàm phân tích toàn diện 1 phiếu:
    Trả về cấu trúc chuẩn:
    - is_outbound_block: bool
    - carriers: list
    - carrier_display: str
    - has_commitment: bool
    - commitment_display: str
    - commitment_source: str
    - commitment_files: list of dict [{"name": "...", "url": "..."}]
    - summary: str
    """
    title = str(package_title or "").strip()
    content = str(ticket_content or "").strip()

    is_block = is_outbound_block_ticket(title, content)
    carriers = extract_carriers(content, title)
    commit_info = extract_commitment_info(content, ccos_attachments)
    summary = summarize_spam_call(title, content, carriers, commit_info, phone=phone)

    carrier_display = ", ".join(carriers) if carriers else ("Ngoại mạng" if is_block else "--")

    return {
        "is_outbound_block": is_block,
        "carriers": carriers,
        "carrier_display": carrier_display,
        "has_commitment": commit_info["has_commitment"],
        "commitment_display": commit_info["display"],
        "commitment_source": commit_info["source"],
        "commitment_files": commit_info["files"],
        "summary": summary
    }
