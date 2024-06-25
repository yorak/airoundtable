from os import path
from sys import stderr, exit
import json
from random import choice, randint

try:
    from openai import OpenAI as LLM
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
except:
    print("Error: The environment is not set up correctly.", file=sys.stderr)
    print("Ensure you have created and activated the correct virtual environment.", file=sys.stderr)
    print('E.g., run "source mistranrtvenv/bin/activate" in your terminal', file=sys.stderr)
    exit(1)

# The more roulette slots there are, the more infrequent the event is.
# Can be interpreted to control to "do/change, in average, after this many turns".
TOPIC_CHANGE_FREQ_ROULETTE_SLOTS = 4 # Controls how often a random new question is chosen
ASK_OPINION_ROULETTE_SLOTS = 4 # Controls how often agents are prompted to ask for opinions of others

GIVE_INTRODUCTIONS = True # If the participants are introduced to each other before the roundtable starts
DISCUSSION_LENGTH = 20 # Controls how many turns of speech.
WRAP_UP_TURNS = 3 # Allow this many turns for the agents to wrap up.

# Some pieces of the prompt, mind the whitespace to avoid messy formatting
FILLER_MESSAGE = "This has been an intriguing discussion so far. Let's continue."
LIST_PARTICIPANTS = "The discussion is between "
GIVE_TOPIC_THEME = " The discussion revolves around "
GIVE_NEW_TOPIC = "\n\nYou are now discussing on "
ASK_2ND_OPINION = " Acknowledge the ideas of others and occasionally ask for second opinion. "
TIME_INFO = " You have {} minutes left."
WRAP_UP = " Time to wrap up!"

# Controls the output
VERBOSITY = 0
TEXT_COLORS = [Fore.RED,
               Fore.GREEN,
               Fore.YELLOW,
               Fore.BLUE,
               Fore.MAGENTA,
               Fore.CYAN,
               Fore.WHITE]

# Use the agent from here
client = LLM(
    api_key="EMPTY",
    base_url="http://localhost:8000/v1"
)

#########################
# SOME HELPER FUNCTIONS #
#########################

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
        filename = f"participants/role{pid}.json"
        if not path.exists(filename):
            break
        with open(filename, "r") as file:
            participant = json.load(file)
            participant['color'] = TEXT_COLORS[pid]
            participants.append(participant)
    return participants

def massage_to_expected_back_and_forth_format(messages):
    """ Some models require alternating user and assistant roles in the messages list.
    Hence, sometimes a filler is needed and this sentence is used. """
    for i, m in enumerate(messages):
        m['role'] = 'user' if i%2==0 else 'assistant'
    if  messages and messages[-1]['role']=='user':
        messages.append({'role': 'assistant', 'content': FILLER_MESSAGE})
        return True
    return False

def print_introductions_for(participants):
    for p in participants:
        print( "\n", p['color']+(
            p['full_name']+" "+
            remove_first_sentence_and_word(p['prompt'])) )
    print()


##########################
# THE MAIN SCRIPT STARTS #
##########################

# Get participants.
participants = read_participants()
names = [p['name'] for p in participants]
names_string = ', '.join(names[:-1]) + ' and ' + names[-1] if len(names) > 1 else ''.join(names)

# Read context
context = ""
with open("task/context.txt", "r") as file:
    context  = file.read().strip()

# Read general instuctions
instructions = ""
with open("task/instructions.txt", "r") as file:
    instructions  = file.read().strip()

# Read questions
questions = []
with open("task/questions.txt", "r") as file:
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
        prompt+=LIST_PARTICIPANTS+names_string+"."
        if GIVE_INTRODUCTIONS:
            print_introductions_for(participants)
        print(GIVE_TOPIC_THEME+questions[0])

    # Choose a random person to speak, if no participant was expliclity asked to contribute
    participant = choice(participants) if not next_participant else next_participant
    if participant==prev_participant:
        # Avoid twice per row, but it is not a hard constraint
        participant = choice(participants)

    nametag = participant['name']+":"
    prev_participant = participant
    prompt+="\n\n"+participant['prompt']

    # Check if it is time to choose another question.
    if not topic or randint(0, TOPIC_CHANGE_FREQ_ROULETTE_SLOTS): 
        topic = choice(questions)
        prompt+=GIVE_NEW_TOPIC+topic.strip()
    
    prompt+="\n\n"+instructions
    if randint(0,ASK_OPINION_ROULETTE_SLOTS)==0:
        prompt+=ASK_2ND_OPINION
    prompt += TIME_INFO.format(turns_left)
    if turns_left<=WRAP_UP_TURNS:
        prompt+=WRAP_UP
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
    messages.pop() # pop the (user) prompt
    if added_dummy:
        messages.pop()
        added_dummy = False
    messages.append({'role': 'assistant', 'content': reply})

# TODO: Use the LLM to summarize the discussion and lift 3-5 main points from there.
