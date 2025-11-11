"""
파일 처리 유틸리티 (PDF, 이미지 등)
"""
import io
import os
import PyPDF2
from PIL import Image
import pytesseract
import hashlib
import threading
import openai
import base64
import time
from pdf2image import convert_from_bytes


# 이미지 분석 캐시 (중복 실행 방지)
_image_analysis_cache = {}
_image_analysis_locks = {}
_cache_lock = threading.Lock()


def extract_text_from_pdf(file_content):
    """PDF에서 텍스트 추출 (직접 추출 + OCR 백업)"""
    try:
        pdf_file = io.BytesIO(file_content)
        pdf_reader = PyPDF2.PdfReader(pdf_file)
        text = ""
        
        # 먼저 직접 텍스트 추출 시도
        for page_num in range(len(pdf_reader.pages)):
            page = pdf_reader.pages[page_num]
            page_text = page.extract_text()
            text += page_text + "\n"
        
        # 추출된 텍스트가 충분하지 않으면 OCR 시도
        if len(text.strip()) < 100:  # 텍스트가 너무 적으면 OCR 사용
            print("PDF 직접 추출 텍스트가 부족하여 OCR을 사용합니다.")
            return extract_text_from_pdf_ocr(file_content)
        
        return text.strip()
    except Exception as e:
        print(f"PDF 직접 추출 실패, OCR을 사용합니다: {str(e)}")
        return extract_text_from_pdf_ocr(file_content)


def extract_text_from_pdf_ocr(file_content):
    """PDF를 이미지로 변환 후 OCR로 텍스트 추출"""
    try:
        # PDF를 이미지로 변환
        images = convert_from_bytes(file_content, dpi=300)
        all_text = ""
        
        for i, image in enumerate(images):
            # 간단한 이미지 전처리 (NumPy 없이)
            # 이미지를 그레이스케일로 변환
            if image.mode != 'L':
                image = image.convert('L')
            
            # OCR 수행 (전처리 없이)
            page_text = pytesseract.image_to_string(image, lang='kor+eng')
            all_text += f"\n--- 페이지 {i+1} ---\n{page_text}\n"
        
        return all_text.strip()
    except Exception as e:
        return f"PDF OCR 처리 중 오류 발생: {str(e)}"


def extract_text_from_image(file_content):
    """이미지에서 OCR을 사용하여 텍스트 추출"""
    try:
        # 이미지 열기
        image = Image.open(io.BytesIO(file_content))
        
        # 이미지 전처리 (간단한 방식)
        if image.mode != 'L':
            image = image.convert('L')  # 그레이스케일로 변환
        
        # OCR 수행 (한국어 + 영어)
        text = pytesseract.image_to_string(image, lang='kor+eng')
        
        return text.strip()
    except Exception as e:
        return f"이미지 텍스트 추출 중 오류 발생: {str(e)}"


def process_uploaded_file(file):
    """업로드된 파일 처리"""
    try:
        # 파일 포인터를 처음으로 이동
        if hasattr(file, 'seek'):
            file.seek(0)
        file_content = file.read()
        
        if not file_content:
            print(f"⚠️ 파일 내용이 비어있습니다: {file.name}")
            return "파일 내용을 읽을 수 없습니다."
        
        file_extension = file.name.split('.')[-1].lower()
        
        if file_extension == 'pdf':
            extracted_text = extract_text_from_pdf(file_content)
            print(f"✅ PDF 텍스트 추출 완료: {len(extracted_text)}자")
            if len(extracted_text.strip()) < 50:
                print(f"⚠️ 추출된 텍스트가 매우 짧습니다. OCR을 시도할 수 있습니다.")
            return extracted_text
        elif file_extension in ['jpg', 'jpeg', 'png', 'bmp', 'tiff']:
            # 이미지 파일의 경우 파일 경로를 반환 (Ollama가 직접 읽도록)
            return f"IMAGE_FILE:{file.name}"
        else:
            return "지원하지 않는 파일 형식입니다. PDF 또는 이미지 파일을 업로드해주세요."
    except Exception as e:
        print(f"❌ 파일 처리 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        return f"파일 처리 중 오류가 발생했습니다: {str(e)}"


def summarize_content(content, api_key=None, file_path=None, full_content=False):
    """내용을 요약하는 함수 (Ollama 사용)
    
    Args:
        content: 텍스트 내용 또는 IMAGE_FILE: 접두사가 있는 이미지 파일명
        api_key: API 키 (사용하지 않음)
        file_path: 이미지 파일 경로
        full_content: True면 전체 내용을 반환, False면 요약만 반환
    """
    import ollama
    
    try:
        # 이미지 파일인지 확인
        if content.startswith("IMAGE_FILE:"):
            if file_path and os.path.exists(file_path):
                return analyze_image_with_ollama(file_path)
            else:
                return "이미지 파일을 찾을 수 없습니다."
        
        # 텍스트 내용인 경우
        if full_content:
            # 전체 내용을 반환하되, 너무 길면 일부만 (최대 50000자)
            if len(content) > 50000:
                print(f"⚠️ 텍스트가 너무 깁니다 ({len(content)}자). 처음 50000자만 사용합니다.")
                return content[:50000] + "\n\n...(내용이 길어 일부만 표시됩니다)..."
            return content
        
        # 요약 모드: 내용이 너무 길면 자르기 (토큰 제한 고려)
        if len(content) > 12000:
            content = content[:12000] + "..."
        
        # 요약 프롬프트
        prompt = f"""당신은 문서 내용을 요약하는 전문가입니다. 

주어진 내용이 PDF에서 추출된 텍스트인 경우:
- OCR 오류나 불완전한 텍스트가 있을 수 있음을 고려
- 가능한 한 원문의 의도를 파악하여 요약
- 중요한 정보는 보존하되 간결하게 정리

요약 시 다음을 포함해주세요:
1. 문서의 주요 주제/목적
2. 핵심 내용과 중요한 포인트
3. 결론이나 요약 (있는 경우)

원문의 주요 내용을 보존하면서도 간결하게 작성해주세요.

다음 내용을 요약해주세요:

{content}"""
        
        # Ollama 클라이언트로 요약 수행
        response = ollama.chat(
                   model='llama3.2:latest',  # 또는 사용 가능한 다른 모델
            messages=[
                {
                    'role': 'user',
                    'content': prompt
                }
            ],
            options={
                'temperature': 0.3,
                'num_predict': 1500
            }
        )
        
        return response['message']['content']
    except Exception as e:
        print(f"Ollama 요약 오류: {str(e)}")
        # Ollama 실패 시 기본 요약
        if len(content) > 1000:
            return f"문서 요약 (Ollama 오류로 간단 요약): {content[:500]}..."
        return content


def analyze_image_with_ollama(image_path):
    """이미지 분석 (GPT-4o-mini 사용, 중복 실행 방지)"""
    try:
        # 파일 해시 계산 (중복 실행 방지)
        file_hash = None
        if os.path.exists(image_path):
            with open(image_path, 'rb') as f:
                file_hash = hashlib.md5(f.read()).hexdigest()
        
        # 캐시 확인 및 동시 요청 제어
        image_lock = None  # 함수 레벨 변수로 선언
        if file_hash:
            with _cache_lock:
                if file_hash in _image_analysis_cache:
                    cached_result = _image_analysis_cache[file_hash]
                    print(f"⚡ 이미지 분석 캐시 히트! (해시: {file_hash[:8]}...)")
                    return cached_result
                
                # 동일한 이미지에 대한 동시 요청이 있으면 Lock 생성
                if file_hash not in _image_analysis_locks:
                    _image_analysis_locks[file_hash] = threading.Lock()
            
            # 동일한 이미지에 대한 동시 요청 대기 (Lock 획득)
            image_lock = _image_analysis_locks[file_hash]
            acquired = image_lock.acquire(blocking=True, timeout=120)  # 최대 120초 대기 (분석 시간 고려)
            if not acquired:
                print(f"⚠️ 이미지 분석 Lock 획득 실패 (타임아웃 120초)")
                # Lock이 해제되지 않은 경우 강제로 정리
                with _cache_lock:
                    if file_hash in _image_analysis_locks:
                        try:
                            if _image_analysis_locks[file_hash].locked():
                                _image_analysis_locks[file_hash].release()
                                print(f"🔓 타임아웃으로 인한 Lock 강제 해제")
                        except:
                            pass
                return "이미지 분석 중 다른 요청이 처리 중입니다. 잠시 후 다시 시도해주세요."
            
            try:
                # Lock 획득 후 다시 캐시 확인 (다른 스레드가 이미 완료했을 수 있음)
                with _cache_lock:
                    if file_hash in _image_analysis_cache:
                        print(f"⚡ 이미지 분석 캐시 히트! (대기 중 다른 요청이 완료함)")
                        image_lock.release()
                        return _image_analysis_cache[file_hash]
                
                # Lock을 획득했고 캐시에도 없으므로 실제 분석 수행
                print(f"🖼️ 이미지 분석 시작: {image_path} (Lock 획득, 실제 분석 수행)")
                if file_hash:
                    print(f"🔑 파일 해시: {file_hash[:16]}...")
                
            except Exception as lock_error:
                if image_lock and image_lock.locked():
                    image_lock.release()
                    print(f"🔓 Lock 해제 (예외 발생)")
                raise
        else:
            print(f"🖼️ 이미지 분석 시작: {image_path} (해시 없음, 직접 분석)")
        
        print(f"📁 파일 존재 여부: {os.path.exists(image_path)}")
        if os.path.exists(image_path):
            file_size = os.path.getsize(image_path)
            print(f"📏 파일 크기: {file_size} bytes")
        
        # GPT-4o-mini를 직접 사용
        print(f"🚀 GPT-4o-mini로 이미지 분석 시작")
        print(f"📁 이미지 경로: {image_path}")
        
        ollama_response = ""
        ollama_success = False
        
        # GPT-4o-mini로 직접 분석
        try:
            openai_api_key = os.getenv('OPENAI_API_KEY')
            
            if not openai_api_key:
                print(f"❌ OPENAI_API_KEY가 설정되지 않았습니다.")
                ollama_response = "OpenAI API 키가 설정되지 않았습니다."
            else:
                print(f"🔄 GPT-4o-mini로 이미지 분석 시도 중...")
                gpt_start_time = time.time()
                
                # 이미지를 base64로 인코딩
                with open(image_path, "rb") as image_file:
                    base64_image = base64.b64encode(image_file.read()).decode('utf-8')
                
                # GPT-4o-mini Vision API 호출
                client = openai.OpenAI(api_key=openai_api_key)
                response = client.chat.completions.create(
                    model="gpt-4o-mini",
                    messages=[
                        {
                            "role": "user",
                            "content": [
                                {
                                    "type": "text",
                                    "text": """Analyze this image in detail. Include:
1. All visible text (read exactly as shown, including any text in the image)
2. Visual content (objects, colors, composition, style)
3. Overall meaning or message

Be thorough but concise. Make sure to read and include ALL text visible in the image."""
                                },
                                {
                                    "type": "image_url",
                                    "image_url": {"url": f"data:image/jpeg;base64,{base64_image}"}
                                }
                            ]
                        }
                    ],
                    max_tokens=500,
                    temperature=0.1
                )
                
                gpt_elapsed = time.time() - gpt_start_time
                ollama_response = response.choices[0].message.content
                ollama_success = True
                print(f"✅ GPT-4o-mini 분석 성공! (소요 시간: {gpt_elapsed:.2f}초)")
                print(f"📄 GPT-4o-mini 분석 결과:\n{ollama_response}")
                
        except Exception as gpt_error:
            print(f"❌ GPT-4o-mini 분석 실패: {str(gpt_error)}")
            import traceback
            traceback.print_exc()
            ollama_response = "이미지 분석에 실패했습니다. OpenAI API를 확인해주세요."
        
        # GPT-4o-mini 분석 결과 반환
        result = None
        if ollama_response and len(ollama_response.strip()) > 0:
            print(f"✅ GPT-4o-mini 이미지 분석 완료: 총 {len(ollama_response)}자")
            result = f"[Image Analysis (English)]\n{ollama_response}"
        else:
            error_msg = "이미지 분석 중 오류가 발생했습니다. OpenAI API를 확인해주세요."
            print(f"❌ {error_msg}")
            result = error_msg
        
        # 결과를 캐시에 저장 (성공한 경우만)
        if file_hash and result and "오류" not in result and "실패" not in result:
            with _cache_lock:
                _image_analysis_cache[file_hash] = result
                # 캐시 크기 제한 (최대 100개)
                if len(_image_analysis_cache) > 100:
                    oldest_key = next(iter(_image_analysis_cache))
                    del _image_analysis_cache[oldest_key]
                    if oldest_key in _image_analysis_locks:
                        del _image_analysis_locks[oldest_key]
                print(f"💾 이미지 분석 결과 캐시에 저장됨 (해시: {file_hash[:8]}...)")
        
        # Lock 해제 (분석 완료 후)
        if file_hash and image_lock and image_lock.locked():
            try:
                image_lock.release()
                print(f"🔓 이미지 분석 Lock 해제 (분석 완료, 해시: {file_hash[:8]}...)")
            except Exception as release_error:
                print(f"⚠️ Lock 해제 중 오류: {release_error}")
        
        return result
            
    except Exception as e:
        print(f"❌ 이미지 분석 오류: {str(e)}")
        import traceback
        traceback.print_exc()
        error_result = f"이미지 분석 중 오류가 발생했습니다: {str(e)}"
        
        # Lock 해제 (에러 발생 시에도)
        if file_hash and image_lock and image_lock.locked():
            try:
                image_lock.release()
                print(f"🔓 이미지 분석 Lock 해제 (에러 발생, 해시: {file_hash[:8]}...)")
            except Exception as release_error:
                print(f"⚠️ Lock 해제 중 오류: {release_error}")
        
        return error_result

