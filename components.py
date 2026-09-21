"""Streamlit埋め込みコンポーネント。"""

from __future__ import annotations

import json

import streamlit as st


def render_audio_player(playlist: list[dict[str, str]]) -> None:
    """端末テーマに追従する読み上げプレイヤーを描画する。"""
    if not playlist:
        return

    playlist_json = json.dumps(playlist, ensure_ascii=False).replace("</", "<\\/")
    st.iframe(
        f"""
        <style>
            :root {{ color-scheme: light dark; --surface: #f8fafc; --text: #1f2937;
                --muted: #4b5563; --secondary: #e2e8f0; --secondary-text: #1f2937;
                --accent: #047857; --danger: #b91c1c; --border: #cbd5e1; }}
            @media (prefers-color-scheme: dark) {{ :root {{ --surface: #172033; --text: #f3f4f6;
                --muted: #cbd5e1; --secondary: #334155; --secondary-text: #f3f4f6;
                --accent: #047857; --danger: #b91c1c; --border: #475569; }} }}
            * {{ box-sizing: border-box; }}
            body {{ margin: 0; color: var(--text); font-family: system-ui, sans-serif; }}
            .player {{ padding: 20px; background: var(--surface); border: 1px solid var(--border); border-radius: 12px; }}
            h3 {{ margin-top: 0; color: var(--text); }}
            #current-text {{ min-height: 100px; margin: 15px 0; color: var(--text); font-size: 18px; line-height: 1.6; }}
            .controls {{ display: flex; gap: 10px; margin-top: 20px; }}
            button {{ flex: 1; min-height: 44px; padding: 10px; color: var(--secondary-text);
                background: var(--secondary); border: 1px solid var(--border); border-radius: 8px; cursor: pointer; }}
            #play-btn {{ flex: 2; color: white; font-weight: 700; background: var(--accent); }}
            .counter {{ margin-top: 15px; color: var(--muted); font-size: 14px; text-align: center; }}
            @media (max-width: 480px) {{ .controls {{ flex-wrap: wrap; }} button, #play-btn {{ flex: 1 1 100%; }} }}
        </style>
        <div class="player">
            <h3 id="current-title">待機中...</h3>
            <div id="current-text">再生ボタンを押して開始してください</div>
            <div class="controls">
                <button type="button" onclick="prevTrack()">⏮ 前へ</button>
                <button type="button" id="play-btn" onclick="togglePlay()">▶ 再生</button>
                <button type="button" onclick="nextTrack()">次へ ⏭</button>
            </div>
            <div class="counter"><span id="current-index">0</span> / <span id="total-count">0</span></div>
        </div>
        <script>
            const playlist = {playlist_json};
            let currentIndex = 0;
            let isPlaying = false;
            const synth = window.speechSynthesis;
            let currentUtterance = null;
            const titleEl = document.getElementById('current-title');
            const textEl = document.getElementById('current-text');
            const indexEl = document.getElementById('current-index');
            const playBtn = document.getElementById('play-btn');
            document.getElementById('total-count').textContent = playlist.length;

            function updateDisplay() {{
                if (!playlist.length) return;
                const track = playlist[currentIndex];
                titleEl.textContent = track.title || '無題';
                textEl.textContent = track.text;
                indexEl.textContent = currentIndex + 1;
            }}
            function speak() {{
                if (!playlist.length) return;
                synth.cancel();
                const track = playlist[currentIndex];
                currentUtterance = new SpeechSynthesisUtterance(track.text.replace(/_+/g, '空欄'));
                currentUtterance.lang = 'ja-JP';
                currentUtterance.rate = 1.0;
                currentUtterance.onend = function() {{
                    if (isPlaying) setTimeout(() => {{ if (isPlaying) nextTrack(); }}, 1500);
                }};
                currentUtterance.onerror = event => console.error('Speech synthesis error', event);
                synth.speak(currentUtterance);
            }}
            function togglePlay() {{
                if (!playlist.length) return;
                if (isPlaying) {{
                    isPlaying = false; synth.cancel(); playBtn.textContent = '▶ 再生';
                    playBtn.style.background = 'var(--accent)';
                }} else {{
                    isPlaying = true; playBtn.textContent = '⏸ 一時停止';
                    playBtn.style.background = 'var(--danger)'; speak();
                }}
            }}
            function nextTrack() {{
                if (currentIndex < playlist.length - 1) {{
                    currentIndex++; updateDisplay(); if (isPlaying) speak();
                }} else {{
                    isPlaying = false; playBtn.textContent = '▶ 再生(終了)';
                    playBtn.style.background = 'var(--accent)';
                }}
            }}
            function prevTrack() {{
                if (currentIndex > 0) {{ currentIndex--; updateDisplay(); if (isPlaying) speak(); }}
            }}
            updateDisplay();
        </script>
        """,
        height=400,
    )
