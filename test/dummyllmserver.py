import markovify
from flask import Flask, request, jsonify
import re
from random import randint

app = Flask(__name__)


def clean_content(content):
    content = content.replace(':', ',').replace('\n', ' ')
    content = re.sub(' +', ' ', content)
    return content

def remove_duplicate_and_degenerate_sentences(text):
    sentences = re.split(r'(?<=[.,])', text)
    cleaned_sentences = [sentence.strip() + delimiter for sentence, delimiter in zip(sentences, sentences[1:] + ['']) if len(sentence.strip()) > 0]
    unique_good_sentences = list(s for s in dict.fromkeys(cleaned_sentences) if len(s.strip()) > 50)
    return ' '.join(unique_good_sentences)

def generate_response(prompt, max_tokens):
    corpus = remove_duplicate_and_degenerate_sentences(prompt)
    text_model = markovify.Text(corpus)
    response_text = ""
    while True:
         new_sentence = text_model.make_sentence(tries=100) or \
                        text_model.make_short_sentence(max(10, int(max_tokens/10)))
         if new_sentence is None or (response_text!="" and len(new_sentence)+1+len(response_text)>max_tokens):
             break
         response_text+=(" "+new_sentence)

    return {
        "id": "dummy-id",
        "object": "text_completion",
        "created": 1234567890,
        "model": "text-davinci-003",
        "choices": [{
            "message": {
                 "content":response_text
            },
            "index": 0,
            "logprobs": None,
            "finish_reason": "length" if len(response_text) >= max_tokens else "complete"
        }],
        "usage": {
            "prompt_tokens": len(prompt.split()),
            "completion_tokens": len(response_text.split()),
            "total_tokens": len(prompt.split()) + len(response_text.split())
        }
    }


@app.route('/v1/chat/completions', methods=['POST'])
def completions():
    data = request.json
    messages = data.get('messages', [])
    prompt = '\n\n'.join(
        clean_content(message['content']) for message in messages
    )
    max_tokens = data.get('max_tokens', randint(250, 1500))
    response = generate_response(prompt, max_tokens)
    return jsonify(response)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
