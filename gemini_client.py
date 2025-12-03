import google.generativeai as genai
import json
import typing_extensions as typing

class Flashcard(typing.TypedDict):
    question: str
    answer: str

class FlashcardList(typing.TypedDict):
    flashcards: list[Flashcard]

def generate_flashcards(text, api_key, keywords=None):
    """
    Generates flashcards using Gemini API.
    
    Args:
        text (str): The source text.
        api_key (str): The Gemini API key.
        keywords (str, optional): Comma-separated keywords to focus on.
        
    Returns:
        list: A list of dictionaries with 'question' and 'answer'.
    """
    if not api_key:
        return []

    genai.configure(api_key=api_key)
    
    # Use a model that supports JSON mode. 
    model_name = "gemini-2.5-flash"
    
    try:
        model = genai.GenerativeModel(model_name)
        
        keyword_instruction = ""
        if keywords:
            keyword_instruction = f"""
            以下のキーワードに関連する箇所を優先的に穴埋め問題にしてください:
            キーワード: {keywords}
            もしキーワードがテキストに含まれていない場合は、テキスト内の他の重要な用語を使用してください。
            """
        
        prompt = f"""
        あなたは専門的な教師です。以下のテキストに基づいて、穴埋め式の暗記カードを5つ作成してください。
        'question' は、重要な用語を '______' に置き換えた文章にしてください。
        'answer' は、その欠けている重要な用語にしてください。
        日本語で出力してください。
        {keyword_instruction}
        
        テキスト:
        {text}
        """
        
        response = model.generate_content(
            prompt,
            generation_config=genai.GenerationConfig(
                temperature=0.2,
                top_p=0.95,
                top_k=40,
                response_mime_type="application/json",
                response_schema=FlashcardList
            )
        )
        
        result = json.loads(response.text)
        return result.get("flashcards", [])

    except Exception as e:
        print(f"Error generating flashcards: {e}")
        return None
