"""
This script runs remotely on COMPS.
"""
import json
import cowsay

def main():
    with open('trial_index.json', 'r') as f:
        index = json.load(f)
    with open('trials.jsonl', 'r') as f:
        for cnt, line in enumerate(f):
            data = json.loads(line)
            if cnt == index['trial_index']:
                message = data['messages']
                cowsay.cow(message)
                break

if __name__ == '__main__':
    main() 