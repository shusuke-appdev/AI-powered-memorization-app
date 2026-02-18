import json

import streamlit.components.v1 as components


def render_audio_player(playlist):
    """
    オーディオプレイヤーコンポーネントをレンダリングする

    Args:
        playlist (list): 再生するアイテムのリスト [{"title": "...", "text": "..."}, ...]
    """
    if not playlist:
        return

    # JSON化してJavaScriptに渡す
    playlist_json = json.dumps(playlist, ensure_ascii=False)

    components.html(
        f"""
        <div style="padding: 20px; background: #f8f9fa; border-radius: 12px; border: 1px solid #e5e7eb;">
            <h3 id="current-title" style="margin-top: 0; color: #1f2937;">待機中...</h3>
            <div id="current-text" style="font-size: 18px; margin: 15px 0; min-height: 100px; line-height: 1.6; color: #374151;">
                再生ボタンを押して開始してください
            </div>
            
            <div style="display: flex; gap: 10px; margin-top: 20px;">
                <button onclick="prevTrack()" style="flex: 1; padding: 10px; border-radius: 8px; border: none; background: #e5e7eb; cursor: pointer;">\u23ee 前へ</button>
                <button id="play-btn" onclick="togglePlay()" style="flex: 2; padding: 10px; border-radius: 8px; border: none; background: #10b981; color: white; font-weight: bold; cursor: pointer;">\u25b6 再生</button>
                <button onclick="nextTrack()" style="flex: 1; padding: 10px; border-radius: 8px; border: none; background: #e5e7eb; cursor: pointer;">次へ \u23ed</button>
            </div>
            
            <div style="margin-top: 15px; font-size: 14px; color: #6b7280; text-align: center;">
                <span id="current-index">0</span> / <span id="total-count">0</span>
            </div>
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
            const totalEl = document.getElementById('total-count');
            const playBtn = document.getElementById('play-btn');

            document.getElementById('total-count').textContent = playlist.length;

            function updateDisplay() {{
                if (playlist.length === 0) return;
                const track = playlist[currentIndex];
                titleEl.textContent = track.title || '無題';
                textEl.textContent = track.text;
                indexEl.textContent = currentIndex + 1;
            }}

            function speak() {{
                if (playlist.length === 0) return;
                
                synth.cancel(); // 前の読み上げをキャンセル
                
                const track = playlist[currentIndex];
                // 空欄(_____)を「空欄」と読み上げるように置換
                const textToSpeak = track.text.replace(/_+/g, '空欄');
                
                currentUtterance = new SpeechSynthesisUtterance(textToSpeak);
                currentUtterance.lang = 'ja-JP';
                currentUtterance.rate = 1.0;

                currentUtterance.onend = function() {{
                    if (isPlaying) {{
                        // 少し間を空けて次へ
                        setTimeout(() => {{
                            if (isPlaying) nextTrack();
                        }}, 1500);
                    }}
                }};

                currentUtterance.onerror = function(event) {{
                    console.error('Speech synthesis error', event);
                }};

                synth.speak(currentUtterance);
            }}

            function togglePlay() {{
                if (playlist.length === 0) return;

                if (isPlaying) {{
                    isPlaying = false;
                    synth.cancel();
                    playBtn.textContent = "\u25b6 再生";
                    playBtn.style.background = "#10b981";
                }} else {{
                    isPlaying = true;
                    playBtn.textContent = "\u23f8 一時停止";
                    playBtn.style.background = "#ef4444";
                    speak();
                }}
            }}

            function nextTrack() {{
                if (currentIndex < playlist.length - 1) {{
                    currentIndex++;
                    updateDisplay();
                    if (isPlaying) speak();
                }} else {{
                    // 最後まで言ったら停止
                    isPlaying = false;
                    playBtn.textContent = "\u25b6 再生(終了)";
                    playBtn.style.background = "#10b981";
                }}
            }}

            function prevTrack() {{
                if (currentIndex > 0) {{
                    currentIndex--;
                    updateDisplay();
                    if (isPlaying) speak();
                }}
            }}

            // 初期表示
            if (playlist.length > 0) {{
                updateDisplay();
            }}
        </script>
        """,
        height=400,
    )
