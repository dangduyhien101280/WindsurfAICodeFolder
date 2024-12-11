class POSTagger:
    def __init__(self):
        # More comprehensive special cases
        self.special_cases = {
            'sung': ['VERB', 'NOUN'],
            'welcome': ['NOUN', 'VERB', 'ADJECTIVE'],
            'music': ['NOUN']
        }
        
        # Linguistic rules for more accurate tagging
        self.verb_indicators = {
            'endings': ['ed', 'ing', 'es', 'en'],
            'prefixes': ['re', 'un', 'dis'],
        }
        
        self.noun_indicators = {
            'endings': ['ness', 'ment', 'ship', 'dom', 'hood', 'ity'],
            'prefixes': ['un', 'dis'],
        }

    def tag_pos(self, word):
        # Check special cases first
        if word.lower() in self.special_cases:
            return self.special_cases[word.lower()]
        
        # Initialize possible tags
        possible_tags = []
        
        # Verb detection
        if any(word.endswith(ending) for ending in self.verb_indicators['endings']) or \
           any(word.startswith(prefix) for prefix in self.verb_indicators['prefixes']):
            possible_tags.append('VERB')
        
        # Noun detection
        if any(word.endswith(ending) for ending in self.noun_indicators['endings']) or \
           any(word.startswith(prefix) for prefix in self.noun_indicators['prefixes']):
            possible_tags.append('NOUN')
        
        # Context-based additional rules
        if word[0].isupper():
            possible_tags.append('PROPER_NOUN')
        
        # Fallback
        if not possible_tags:
            possible_tags = ['NOUN']  # Default to noun
        
        return possible_tags

def main():
    # Create tagger instance
    tagger = POSTagger()
    
    # Comprehensive test words
    test_words = [
        'sung', 'welcome', 'music',  # Original words
        'happiness', 'running',      # Noun and Verb with typical endings
        'unbelievable', 'dislike',   # Words with prefixes
        'John'                       # Proper noun
    ]
    
    print("Comprehensive POS Tagging:")
    for word in test_words:
        pos_tags = tagger.tag_pos(word)
        print(f"{word}: {', '.join(pos_tags)}")

if __name__ == "__main__":
    main()
