import os
import json
import asyncio
import textwrap
import time
import fitz  # PyMuPDF
from pptx import Presentation
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from pydantic import BaseModel
from google import genai
from google.genai import types

try:
    from moviepy import ImageClip, AudioFileClip, concatenate_videoclips
except ImportError:
    from moviepy.editor import ImageClip, AudioFileClip, concatenate_videoclips


class SlideSummary(BaseModel):
    slide_number: int
    title: str
    key_points: list[str]
    narration_script: str


class LectureScript(BaseModel):
    overall_summary: str
    slides: list[SlideSummary]


def extract_from_pdf(pdf_path: str, output_dir: str) -> list[dict]:
    doc = fitz.open(pdf_path)
    slides_data = []

    for idx, page in enumerate(doc):
        text = page.get_text("text").strip()
        pix = page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5))
        img_path = os.path.join(output_dir, f"slide_{idx + 1}.png")
        pix.save(img_path)

        slides_data.append({
            "slide_number": idx + 1,
            "raw_text": text if text else f"Visual content on slide {idx + 1}",
            "image_path": img_path
        })
    doc.close()
    return slides_data


def render_clean_slide_image(title: str, bullets: list[str], img_path: str):
    img = Image.new("RGB", (1280, 720), color=(10, 15, 30))
    draw = ImageDraw.Draw(img)

    draw.rectangle([(0, 0), (1280, 140)], fill=(20, 27, 45))
    draw.rectangle([(0, 135), (1280, 140)], fill=(99, 102, 241))

    font_title = ImageFont.load_default(size=36)
    font_body = ImageFont.load_default(size=26)

    draw.text((65, 45), title[:55], fill=(255, 255, 255), font=font_title)

    y_offset = 190
    for idx, point in enumerate(bullets[:4]):
        draw.ellipse([65, y_offset + 8, 81, y_offset + 24], fill=(129, 140, 248))
        
        wrapped = textwrap.wrap(point, width=65)
        for line in wrapped:
            draw.text((105, y_offset), line, fill=(226, 232, 240), font=font_body)
            y_offset += 42
        y_offset += 15

    img.save(img_path)


def extract_from_pptx(pptx_path: str, output_dir: str) -> list[dict]:
    prs = Presentation(pptx_path)
    slides_data = []

    for idx, slide in enumerate(prs.slides):
        texts = []
        for shape in slide.shapes:
            if hasattr(shape, "text") and shape.text.strip():
                texts.append(shape.text.strip())
        combined_text = "\n".join(texts)
        img_path = os.path.join(output_dir, f"slide_{idx + 1}.png")

        slides_data.append({
            "slide_number": idx + 1,
            "raw_text": combined_text if combined_text else f"Slide {idx + 1}",
            "image_path": img_path
        })
    return slides_data


def run_agentic_summarizer(slides_data: list[dict], api_key: str) -> LectureScript:
    """Smart summarizer utilizing Gemini Flash for detailed professor narration."""
    client = genai.Client(api_key=api_key)
    summaries = []

    for s in slides_data:
        lines = [line.strip() for line in s['raw_text'].split('\n') if line.strip()]
        title = lines[0][:50] if lines else f"Slide {s['slide_number']} Overview"
        key_points = lines[1:4] if len(lines) > 1 else ["Core concepts reviewed.", "Important technical takeaway."]
        
        # Default fallback script in case of network issues
        narration_script = f"On slide number {s['slide_number']}, titled {title}, we examine the core architecture and key principles of this topic."

        try:
            prompt = (
                f"You are an expert computer science professor delivering an engaging lecture. "
                f"Explain the following slide content clearly and thoroughly in 2 to 3 natural sentences for audio narration:\n\n"
                f"Slide Title: {title}\n"
                f"Slide Content:\n{s['raw_text'][:800]}"
            )
            response = client.models.generate_content(
                model="gemini-2.5-flash",
                contents=prompt,
            )
            if response and response.text:
                narration_script = response.text.strip().replace('\n', ' ')
        except Exception as e:
            print(f"Gemini API warning on slide {s['slide_number']}: {e}")

        summaries.append(SlideSummary(
            slide_number=s['slide_number'],
            title=title,
            key_points=key_points[:3],
            narration_script=narration_script
        ))

    return LectureScript(
        overall_summary="Presentation deck successfully processed and synthesized into an accurate studio video summary.",
        slides=summaries
    )


async def _synthesize_speech_async(text: str, audio_path: str, voice: str):
    communicate = edge_tts.Communicate(text, voice)
    await communicate.save(audio_path)


def generate_audio(text: str, audio_path: str, voice: str = "en-US-AriaNeural"):
    asyncio.run(_synthesize_speech_async(text, audio_path, voice))


def build_narrated_video(
    slides_data: list[dict],
    lecture_script: LectureScript,
    is_pptx: bool,
    voice: str,
    output_dir: str,
) -> str:
    video_clips = []
    script_map = {s.slide_number: s for s in lecture_script.slides}

    for slide in slides_data:
        num = slide["slide_number"]
        summary_item = script_map.get(num)
        if not summary_item:
            continue

        if is_pptx:
            render_clean_slide_image(
                summary_item.title,
                summary_item.key_points,
                slide["image_path"]
            )

        audio_path = os.path.join(output_dir, f"audio_{num}.mp3")
        generate_audio(summary_item.narration_script, audio_path, voice)

        audio_clip = AudioFileClip(audio_path)
        duration = audio_clip.duration + 0.3

        img_clip = ImageClip(slide["image_path"])
        if hasattr(img_clip, "with_duration"):
            img_clip = img_clip.with_duration(duration).with_audio(audio_clip)
        else:
            img_clip = img_clip.set_duration(duration).set_audio(audio_clip)

        video_clips.append(img_clip)

    final_video = concatenate_videoclips(video_clips, method="compose")
    final_video_path = os.path.join(output_dir, "lecture_summary_video.mp4")

    final_video.write_videofile(
        final_video_path,
        fps=15,
        codec="libx264",
        audio_codec="aac",
        threads=4,
        logger=None
    )
    return final_video_path