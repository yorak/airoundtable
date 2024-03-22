from os import path
from sys import stderr
import json
from random import choice, randint
from openai import OpenAI as LLM
from colorama import init, Fore, Back, Style
init(autoreset=True)

TOPIC_CHANGE_FREQ = 4
ASK_OPINION_RULETTE = 4
DISCUSSION_LENGTH = 20 # how many turns of speech
WRAP_UP_TURNS = 3 #This many turns to wrap up.
VERBOSITY = 0
OUTFILE = "output.txt"
GIVE_INTRODUCTIONS = True

TEXT_COLORS = [Fore.RED,
               Fore.GREEN,
               Fore.YELLOW,
               Fore.BLUE,
               Fore.MAGENTA,
               Fore.CYAN,
               Fore.WHITE]

def remove_first_sentence_and_word(text):
    sentences = text.split('. ')
    if len(sentences) > 1:
        sentences = sentences[1:]
        second_sentence_words = sentences[0].split(' ', 1)
        if len(second_sentence_words) > 1:
            sentences[0] = ' '.join(second_sentence_words[1:])
    modified_text = '. '.join(sentences)
    return modified_text

def read_participants():
    participants = []
    pid = 0
    while True:
        pid+=1
        filename = f"role{pid}.json"
        if not path.exists(filename):
            break
        with open(filename, "r") as file:
            participant = json.load(file)
            participant['color'] = TEXT_COLORS[pid]
            participants.append(participant)
    return participants

def massage_to_expected_back_and_forth_format(messages):
    for i, m in enumerate(messages):
        m['role'] = 'user' if i%2==0 else 'assistant'
    if  messages and messages[-1]['role']=='user':
        messages.append({'role': 'assistant',
            'content': "This has been a good discussion. Let's continue."})
        return True
    return False

def print_introductions_for(participants):
    for p in participants:
        print( "\n", p['color']+(
            p['full_name']+" "+
            remove_first_sentence_and_word(p['prompt'])) )
    print()

client = LLM(
    api_key="EMPTY",
    base_url="http://localhost:8000/v1"
)

# Get participants.
participants = read_participants()
names = [p['name'] for p in participants]
names_string = ', '.join(names[:-1]) + ' and ' + names[-1] if len(names) > 1 else ''.join(names)

# Read context
context = ""
with open("context.txt", "r") as file:
    context  = file.read().strip()

# Read general instuctions
instructions = ""
with open("instructions.txt", "r") as file:
    instructions  = file.read().strip()

# Read questions
questions = []
with open("questions2.txt", "r") as file:
    questions = file.readlines()

# Start the discussion
messages = []
topic = ""
added_dummy = False
next_participant = None
prev_participant = None
for turns_left in range(DISCUSSION_LENGTH, 0, -1):
    # The API assumes back and forth, emulate it  
    added_dummy = massage_to_expected_back_and_forth_format(messages)

    # Build the prompt
    prompt = ""

    if not topic:
        print(context)
        prompt+=context+"\n\n"
        # Introduces the names to agents to give better context.
        prompt+="The discussion is between "+names_string+"."
        if GIVE_INTRODUCTIONS:
            print_introductions_for(participants)
        print(" The discussion revolves around "+questions[0])

    # Choose person to speak
    participant = choice(participants) if not next_participant else next_participant
    if participant==prev_participant:
        # Avoid twice per row, but it is not hard constraint
        participant = choice(participants)
    nametag = participant['name']+":"
    prev_participant = participant
    prompt+="\n\n"+participant['prompt']

    if not topic or randint(0, TOPIC_CHANGE_FREQ): 
        topic = choice(questions)
        prompt+="\n\nYou are now discussing on "+topic.strip()
    
    prompt+="\n\n"+instructions
    if randint(0,ASK_OPINION_RULETTE)==0:
        prompt+=" Acknowledge the ideas of others and occasionally ask for second opinion. "
    prompt+=f" You have {turns_left} minutes left."
    if turns_left<=WRAP_UP_TURNS:
        prompt+=" Time to wrap up!"
    prompt+="\n\n"+nametag+" "

    # Build the call and ask for the completion
    messages.append({'role': 'user', 'content': prompt})
    if VERBOSITY>0:
        print(Style.DIM + ('DEBUG: Prompt the AI with "'+prompt+'"'), file=stderr)
    chat_response = client.chat.completions.create(
        model="mistralai/Mistral-7B-Instruct-v0.2",
        messages=messages,
        temperature=0.7 if not 'creativity' in participant else participant['creativity']
    )
    #TODO: experiment with other parameters? https://docs.vllm.ai/en/latest/dev/sampling_params.html
    
    # Tag who is speaking.
    reply = chat_response.choices[0].message.content.strip()\
            .replace("Assistant:",nametag )
    if not reply.startswith(nametag):
        reply = nametag + " " + reply
    print(participant['color']+reply+"\n\n")

    OUTFILE

    # Check if a name was mentioned in the latter half.
    mentioned_at = -1
    next_participant = None
    for p in participants:
        if p['name'] == participant['name']:
            continue
        pos = reply.rfind(p['name'] )
        if pos>mentioned_at:
            mentioned_at = pos
            next_participant = p
    
    # Manage discussion history
    messages.pop()
    if added_dummy:
        messages.pop()
        added_dummy = False
    messages.append({'role': 'assistant', 'content': reply})