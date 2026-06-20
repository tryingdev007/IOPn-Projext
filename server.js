// server.js — paste a project link in, Gemini reads the page and summarizes it.
// Run with: node server.js   (Node 18+ needed for built-in fetch)

import 'dotenv/config';
import express from 'express';
import cors from 'cors';
import { GoogleGenAI } from '@google/genai';

const app = express();
const PORT = 3000;
const ai = new GoogleGenAI({ apiKey: process.env.GEMINI_API_KEY });

app.use(cors());
app.use(express.static('.')); // serves index.html, style.css, app.js, icons-png from this folder

// Schema Gemini's JSON reply has to match — keeps the response shape predictable.
const responseSchema = {
  type: 'object',
  properties: {
    name: { type: 'string', description: "The project's name." },
    chain: {
      type: 'string',
      description: "Primary blockchain/ecosystem, e.g. Ethereum, Solana, Sui. 'Unknown' if the page doesn't say."
    },
    description: {
      type: 'string',
      description: 'A 2-3 sentence plain-language summary of what the project does, based only on the page content.'
    },
    twitter: {
      type: 'string',
      description: "Link to the project's X/Twitter account if it's linked on the page, otherwise an empty string."
    },
    discord: {
      type: 'string',
      description: "Link to the project's Discord server if it's linked on the page, otherwise an empty string."
    }
  },
  required: ['name', 'chain', 'description', 'twitter', 'discord']
};

// GET /api/analyze?url=https://example.com
app.get('/api/analyze', async (req, res) => {
  const url = (req.query.url || '').trim();

  if (!url) {
    return res.status(400).json({ error: 'Missing ?url= query parameter.' });
  }
  if (!process.env.GEMINI_API_KEY) {
    return res.status(500).json({ error: 'GEMINI_API_KEY is missing. Add it to your .env file.' });
  }

  try {
    const prompt = `Visit this crypto project's webpage and summarize it: ${url}

Based only on what's actually stated on the page, extract:
- name: the project's name
- chain: the primary blockchain/ecosystem it's built on ("Unknown" if the page doesn't say)
- description: a 2-3 sentence plain-language summary of what the project does
- twitter: a link to their X/Twitter account if it's linked on the page, otherwise an empty string
- discord: a link to their Discord server if it's linked on the page, otherwise an empty string

Don't guess or invent anything that isn't actually on the page.`;

    // gemini-2.5-flash is fast/cheap and fine for this. Swap the model name
    // below if your key doesn't have access to it.
    const response = await ai.models.generateContent({
      model: 'gemini-2.5-flash',
      contents: prompt,
      config: {
        tools: [{ urlContext: {} }],
        responseFormat: {
          text: {
            mimeType: 'application/json',
            schema: responseSchema
          }
        }
      }
    });

    // Logged once so you can see exactly what Gemini saw and returned.
    console.log('--- Gemini response for', url, '---');
    console.log(response.text);

    const data = JSON.parse(response.text);
    res.json(data);

  } catch (err) {
    console.error('Gemini error:', err);
    res.status(500).json({ error: 'Something went wrong asking Gemini about that link.' });
  }
});

app.listen(PORT, () => {
  console.log(`Server running — open http://localhost:${PORT}`);
});