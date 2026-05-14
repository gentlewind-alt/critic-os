const MOCK_EVENTS = [
    { type: 'log', content: 'INITIALIZING KERNEL_v4.2...' },
    { type: 'log', content: 'CONNECTING TO NEURO_TONE_CORE...' },
    { type: 'log', content: 'DECRYPTING USER_MUSIC_DNA...' },
    
    // 1. PROFILE ROAST START
    { 
        type: 'profile_start', 
        question_module: {
            question: "Do you listen to Radiohead because you're deep, or because you want people to THINK you're deep?",
            options: { A: "I'm actually deep", B: "It's a lifestyle choice" },
            intent: { A: "confirmed", B: "denied" }
        }
    },
    { type: 'profile_token', text: "Your music taste is a cryogenic sleep of late-90s existential dread mixed with 'main character' pop anthems. " },
    { type: 'profile_token', text: "It’s as if your personality is a Venn diagram between a rainy Tuesday in London and a glitter-bombed stadium tour. " },
    { type: 'profile_token', text: "You’re not just listening to music; you're building a fortress of emotional unavailability." },
    { type: 'profile_end' },

    // 2. SONG 1: RADIOHEAD
    { type: 'coverflow', song: { track: "Everything in Its Right Place", artist: "Radiohead", image: "https://i.scdn.co/image/ab67616d0000b27394a500b5220641047192f168" } },
    { type: 'emotion', data: ['sadness', 'confusion', 'awe'], confidence: 0.89 },
    { type: 'roast_start', index: 0, question_module: {
        question: "Is sucking a lemon really the peak of your emotional range?",
        options: { A: "Yes, unfortunately", B: "It's a metaphor, okay?" },
        intent: { A: "confirmed", B: "denied" }
    }},
    { type: 'roast_token', text: "You put this on and suddenly think your life is a moody A24 film. " },
    { type: 'roast_token', text: "The glitchy synths aren't a personality trait, they're just a digital reflection of your own messy desk. " },
    { type: 'roast_token', text: "Everything is in its right place, except for your ability to hold a conversation." },
    { type: 'evidence', text: "'Yesterday I woke up sucking a lemon'", index: 0 },
    { type: 'roast_end', index: 0 },

    // 3. SONG 2: TAYLOR SWIFT
    { type: 'coverflow', song: { track: "Cruel Summer", artist: "Taylor Swift", image: "https://i.scdn.co/image/ab67616d0000b273e787cffec20aa2a396a61647" } },
    { type: 'emotion', data: ['excitement', 'desire', 'joy'], confidence: 0.94 },
    { type: 'roast_start', index: 1 },
    { type: 'roast_token', text: "From existential dread to stadium pop in three seconds. " },
    { type: 'roast_token', text: "You scream these lyrics in the car to feel something, but the only thing you're feeling is the disappointment of your neighbors. " },
    { type: 'roast_token', text: "It’s a cruel summer for anyone forced to share your Spotify Wrapped." },
    { type: 'evidence', text: "'I love you, ain't that the worst thing you ever heard?'", index: 1 },
    { type: 'roast_end', index: 1 },

    // 4. FINAL VERDICT
    { type: 'final_start', profile: { spectrum: ['sadness', 'joy', 'confusion'], confidence: 0.82 } },
    { type: 'final_token', text: "You are an emotional pendulum swinging between 'it is what it is' and full-blown identity crisis. " },
    { type: 'final_token', text: "Stop using Radiohead to justify your inability to text back and Taylor Swift to justify your bad dating choices. " },
    { type: 'final_token', text: "You're a mess, but at least your playlist has high production value." },
    { type: 'final_end' }
];

// Helper to simulate the stream delay
async function simulateStream(callback) {
    for (const event of MOCK_EVENTS) {
        // Adjust delays based on event type for a natural feel
        let delay = 300 + Math.random() * 500;
        if (event.type.includes('token')) delay = 50 + Math.random() * 50;
        if (event.type.includes('start')) delay = 1500;
        
        await new Promise(r => setTimeout(r, delay));
        await callback(event);
    }
}
