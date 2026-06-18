import os
import requests
import time
from dotenv import load_dotenv

load_dotenv(override=True)

class ResilientBrain:
    def __init__(self):
        self.keys = {
            "groq": os.getenv("GROQ_API_KEY"),
            "google_1": os.getenv("GOOGLE_API_KEY_1") or os.getenv("GOOGLE_API_KEY"),
            "google_2": os.getenv("GOOGLE_API_KEY_2"),
            "google_3": os.getenv("GOOGLE_API_KEY_3"),
            "github": os.getenv("GITHUB_TOKEN"),
            "sambanova": os.getenv("SAMBANOVA_API_KEY"),
            "cerebras": os.getenv("CEREBRAS_API_KEY"),
            "siliconflow": os.getenv("SILICONFLOW_API_KEY"),
            "llm7": os.getenv("LLM7_API_KEY"),
            "hf": os.getenv("HF_API_KEY"),
            "cloudflare": os.getenv("CLOUDFLARE_API_KEY"),
            "mistral": os.getenv("MISTRAL_API_KEY"),
            "cohere": os.getenv("COHERE_API_KEY"),
            "arliai": os.getenv("ARLIAI_API_KEY"),
            "zhipu": os.getenv("ZHIPU_API_KEY"),
            "pollinations": os.getenv("POLLINATIONS_API_KEY")
        }

    def _call_api(self, url, key, model, prompt, temperature, timeout_limit, instruction, is_cloudflare=False):
        if not key: return None, "Missing Key"
        
        key = key.strip()
        url = url.strip()
        model = model.strip()
        
        if "generativelanguage" in url:
            gemini_url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={key}"
            payload = {
                "system_instruction": { "parts": [ { "text": instruction } ] },
                "contents": [ { "parts": [ { "text": prompt } ] } ],
                "generationConfig": {
                    "temperature": temperature,
                    "maxOutputTokens": 8192,
                    "responseMimeType": "application/json"  
                }
            }
            try:
                response = requests.post(gemini_url, json=payload, timeout=timeout_limit)
                if response.status_code == 200:
                    data = response.json()
                    raw_text = data['candidates'][0]['content']['parts'][0]['text']
                    clean_text = raw_text.replace("```json", "").replace("```", "").strip()
                    return clean_text, None
                if response.status_code == 429: return None, "429" 
                return None, f"Status {response.status_code}: {response.text[:150]}"
            except Exception as e:
                return None, str(e)

        headers = {
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        }
        
        if is_cloudflare:
            cf_base = "https://api.cloudflare.com"
            url = f"{cf_base}/client/v4/accounts/{os.getenv('CLOUDFLARE_ACCOUNT_ID', '')}/ai/v1/chat/completions"
        
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": instruction},
                {"role": "user", "content": prompt}
            ],
            "temperature": temperature,
            "max_tokens": 3000 
        }
        
        try:
            response = requests.post(url, headers=headers, json=payload, timeout=timeout_limit)
            if response.status_code == 200:
                data = response.json()
                raw_text = data['choices'][0]['message']['content']
                clean_text = raw_text.replace("```json", "").replace("```", "").strip()

                return data['choices'][0]['message']['content'], None
            if response.status_code == 429: return None, "429" 
            if response.status_code in [404, 410, 502, 503]: return None, f"Offline ({response.status_code})"
            return None, f"Status {response.status_code}: {response.text[:100]}"
        except Exception as e:
            return None, str(e)

    def think(self, prompt, agent_role="general", temperature=0.0):
        if agent_role == "reader":
            sys_instruct = (
                "CRITICAL: You are a Universal Relational Mapper. Output ONLY pure JSON. "
                "You must extract the exact logic circuit from the provided PDF policy. "
                "1. 'logic_gates': Every entry MUST be a 'If/Then' pair. "
                "   - 'condition': The exact trigger rule (e.g., 'Past date', 'Tier 2', 'Tier 3'). "
                "   - 'consequence': The exact required state (e.g., 'Approved', 'PENDING_MANAGER_REVIEW'). "
                "   - 'database_patch_string': The exact string to write to the ledger if triggered (e.g., 'OK', 'Maintenance', or 'null'). "
                "2. 'templates': Extract the notification templates EXACTLY as written in the PDF. "
                "*** CRITICAL EMOJI & HTML PROTOCOL ***\n"
                "You MUST rigorously preserve EVERY single emoji (☑, ❌, ⚠️) and EVERY HTML tag (<b>, <i>). "
                "You MUST use \\n to represent every line break from the PDF. DO NOT squash the template into a single line!"
            )
            dynamic_timeout = 120 
            providers = [
                {"name": "SambaNova (Llama 70B)", "url": "https://api.sambanova.ai/v1/chat/completions", "key": self.keys.get("sambanova"), "model": "Meta-Llama-3.3-70B-Instruct"},
                {"name": "Cerebras (GPT OSS 120B)", "url": "https://api.cerebras.ai/v1/chat/completions", "key": self.keys.get("cerebras"), "model": "gpt-oss-120b"},
                {"name": "Mistral (Large)", "url": "https://api.mistral.ai/v1/chat/completions", "key": self.keys.get("mistral"), "model": "mistral-large-latest"}
            ]

        elif agent_role == "scout":
            sys_instruct = "CRITICAL: You are a Schema Scout. Output ONLY pure JSON focusing on required columns."
            dynamic_timeout = 60
            providers = [
                {"name": "Cerebras (Llama 8B)", "url": "https://api.cerebras.ai/v1/chat/completions", "key": self.keys.get("cerebras"), "model": "llama3.1-8b"},
                {"name": "GitHub (GPT-4o-mini)", "url": "https://models.inference.ai.azure.com/chat/completions", "key": self.keys.get("github"), "model": "gpt-4o-mini"},
                {"name": "Groq (Llama 8B)", "url": "https://api.groq.com/openai/v1/chat/completions", "key": self.keys.get("groq"), "model": "llama-3.1-8b-instant"}
            ]

        elif agent_role == "coder":
            sys_instruct = (
                "CRITICAL: You are an autonomous Data Maintainer API. "
                "Output ONLY pure valid JSON. DO NOT wrap in ```json or markdown.\n"
                "You MUST STRICTLY follow the JSON schema and rules provided in the prompt."
            )
            dynamic_timeout = 90 
            providers = [
                {"name": "Groq (Llama 70B)", "url": "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)", "key": self.keys.get("groq"), "model": "llama-3.3-70b-versatile"},
                {"name": "LLM7 (DeepSeek R1)", "url": "[https://api.llm7.io/v1/chat/completions](https://api.llm7.io/v1/chat/completions)", "key": self.keys.get("llm7"), "model": "deepseek-reasoner"},
                {"name": "Google (Gemini Node 1)", "url": "[https://generativelanguage.googleapis.com](https://generativelanguage.googleapis.com)", "key": self.keys.get("google_1"), "model": "gemini-2.0-flash"},
                {"name": "Pollinations (Fallback)", "url": "[https://text.pollinations.ai/openai/chat/completions](https://text.pollinations.ai/openai/chat/completions)", "key": self.keys.get("pollinations"), "model": "pollinations/any"}
            ]
            
        elif agent_role == "auditor":
            sys_instruct = (
                "CRITICAL: You are the Compliance Auditor API. Output ONLY pure, valid JSON. "
                "*** CRITICAL MATH PROTOCOL ***\n"
                "1. Small models hallucinate decimals. You MUST write your step-by-step logic in a 'thought_process' key.\n"
                "2. Inside your 'excel_updates' array, add 'pass_condition' strictly as 'ActualValue >= Threshold' (e.g., '97.22 >= 98.0'). ALWAYS write the equation for the PASSING state.\n"
                "3. Add 'status_if_pass' (e.g., 'SLA Compliance') and 'status_if_fail' (e.g., 'CRITICAL - SLA Breach').\n"
                "4. TELEGRAM PAYLOAD: Inside 'excel_updates', you MUST add a key 'llm_native_alert' containing the fully formatted HTML Telegram alert for a breach. DO THIS FOR EVERY ROW, even if you think it passes. The system will route it natively."
            )
            dynamic_timeout = 150 
            providers = [
                {"name": "LLM7 (DeepSeek R1)", "url": "[https://api.llm7.io/v1/chat/completions](https://api.llm7.io/v1/chat/completions)", "key": self.keys.get("llm7"), "model": "deepseek-reasoner"},
                {"name": "SambaNova (Llama 70B)", "url": "[https://api.sambanova.ai/v1/chat/completions](https://api.sambanova.ai/v1/chat/completions)", "key": self.keys.get("sambanova"), "model": "Meta-Llama-3.3-70B-Instruct"},
                {"name": "Groq (Llama 70B)", "url": "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)", "key": self.keys.get("groq"), "model": "llama-3.3-70b-versatile"}
            ]
            
        elif agent_role == "gatekeeper":
            sys_instruct = "CRITICAL: You are an Ingestion Gatekeeper. Output pure JSON."
            dynamic_timeout = 30
            providers = [
                {"name": "GitHub (GPT-4o-mini)", "url": "[https://models.inference.ai.azure.com/chat/completions](https://models.inference.ai.azure.com/chat/completions)", "key": self.keys.get("github"), "model": "gpt-4o-mini"},
                {"name": "Groq (Llama 8B)", "url": "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)", "key": self.keys.get("groq"), "model": "llama-3.1-8b-instant"},
                {"name": "Cloudflare (Llama 3B)", "url": "handled_in_call", "key": self.keys.get("cloudflare"), "model": "@cf/meta/llama-3.2-3b-instruct"}
            ]

        elif agent_role == "evaluator":
            sys_instruct = (
                "CRITICAL: You are a strict Policy Adjudicator. Output ONLY pure JSON. "
                "1. Evaluate against the 'logic_gates' IN ORDER from top to bottom. The FIRST matching condition wins. "
                "2. THE TEMPORAL AIRLOCK: Today is April 17. If the requested date is BEFORE April 17 (e.g., 10-Apr), you MUST trigger the 'Retroactive/Past Date' gate. Do not escalate to manager. "
                "3. CATEGORY MATCHING: If the request explicitly states Tier 2 or Tier 3, trigger the Manager Review gate. "
                "4. You MUST output this EXACT format: {\"matched_condition\": \"...\", \"consequence\": \"...\", \"database_patch_string\": \"...\", \"template_reference\": \"...\"}"
            )
            dynamic_timeout = 120
            providers = [
                {"name": "LLM7 (DeepSeek R1)", "url": "[https://api.llm7.io/v1/chat/completions](https://api.llm7.io/v1/chat/completions)", "key": self.keys.get("llm7"), "model": "deepseek-reasoner"},
                {"name": "Cerebras (GLM 4.7)", "url": "[https://api.cerebras.ai/v1/chat/completions](https://api.cerebras.ai/v1/chat/completions)", "key": self.keys.get("cerebras"), "model": "zai-glm-4.7"},
                {"name": "Groq (Llama 70B)", "url": "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)", "key": self.keys.get("groq"), "model": "llama-3.3-70b-versatile"}
            ]

        elif agent_role == "executor":
            sys_instruct = (
                "CRITICAL: You are a strict Transaction Executor. Output ONLY pure JSON. "
                "1. Apply the EXACT 'database_patch_string' provided by the Evaluator. "
                "2. Extract the requested date. You MUST format the column strictly as DD-Mon (e.g., '25-Apr'). "
                "3. FLOW 3 TRANSACTION RULE: You MUST wrap your patch inside an 'excel_micro_patches' array. Do NOT use 'excel_updates'.\n"
                "EXAMPLE: {\"excel_micro_patches\": [{\"target_entity_id\": \"SRV1012\", \"updates\": {\"25-Apr\": \"Maintenance\"}}]}\n"
                "4. ONLY output an empty array [] IF the patch string is 'null' or 'REJECT'."
            )
            dynamic_timeout = 60
            providers = [
                {"name": "Groq (Llama 70B)", "url": "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)", "key": self.keys.get("groq"), "model": "llama-3.3-70b-versatile"},
                {"name": "SambaNova (Llama 70B)", "url": "[https://api.sambanova.ai/v1/chat/completions](https://api.sambanova.ai/v1/chat/completions)", "key": self.keys.get("sambanova"), "model": "Meta-Llama-3.3-70B-Instruct"},
                {"name": "Google (Gemini Node 3)", "url": "[https://generativelanguage.googleapis.com](https://generativelanguage.googleapis.com)", "key": self.keys.get("google_3"), "model": "gemini-2.0-flash"},
                {"name": "GitHub (GPT-4o-mini)", "url": "[https://models.inference.ai.azure.com/chat/completions](https://models.inference.ai.azure.com/chat/completions)", "key": self.keys.get("github"), "model": "gpt-4o-mini"}
            ]
            
        elif agent_role == "fixer":
            sys_instruct = "CRITICAL: You are a JSON repair API. Fix the syntax errors and output pure JSON."
            dynamic_timeout = 60 
            providers = [
                {"name": "Groq (Llama 70B)", "url": "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)", "key": self.keys.get("groq"), "model": "llama-3.3-70b-versatile"},
                {"name": "GitHub (GPT-4o-mini)", "url": "[https://models.inference.ai.azure.com/chat/completions](https://models.inference.ai.azure.com/chat/completions)", "key": self.keys.get("github"), "model": "gpt-4o-mini"},
                {"name": "Google (Gemini Node 2)", "url": "[https://generativelanguage.googleapis.com](https://generativelanguage.googleapis.com)", "key": self.keys.get("google_2"), "model": "gemini-2.0-flash"}
            ]
            
        elif agent_role == "assistant":
            sys_instruct = (
                "You are a Universal Support Assistant. "
                "1. Use the merged DATASET to answer the USER_ASK about a specific entity (Student/Client/Patient). "
                "2. Do NOT guess. If a specific month or metric is not in the data, say so professionally. "
                "3. This system handles multiple domains (Finance, Edu, Health). Use the terms found in the headers. "
                "4. Speak in warm, full sentences. DO NOT use JSON or code blocks."
            )
            dynamic_timeout = 45
            providers = [
                {"name": "GitHub (GPT-4o-mini)", "url": "[https://models.inference.ai.azure.com/chat/completions](https://models.inference.ai.azure.com/chat/completions)", "key": self.keys.get("github"), "model": "gpt-4o-mini"},
                {"name": "Groq (Llama 8B)", "url": "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)", "key": self.keys.get("groq"), "model": "llama-3.1-8b-instant"}
            ]
        else: 
            sys_instruct = "CRITICAL: You are a Concierge Routing API. Output ONLY pure JSON."
            dynamic_timeout = 30 
            providers = [
                {"name": "GitHub (GPT-4o-mini)", "url": "[https://models.inference.ai.azure.com/chat/completions](https://models.inference.ai.azure.com/chat/completions)", "key": self.keys.get("github"), "model": "gpt-4o-mini"},
                {"name": "Groq (Llama 8B)", "url": "[https://api.groq.com/openai/v1/chat/completions](https://api.groq.com/openai/v1/chat/completions)", "key": self.keys.get("groq"), "model": "llama-3.1-8b-instant"}
            ]

        for provider in providers:
            if not provider.get("key") or "your_key_here" in provider["key"]: 
                continue 
            
            if "sambanova" in provider["name"].lower():
                time.sleep(3)    

            is_cf = "cloudflare" in provider["name"].lower()
            
            answer, error = self._call_api(
                provider["url"], provider["key"], provider["model"], 
                prompt, temperature, dynamic_timeout, sys_instruct, is_cloudflare=is_cf
            )
                
            if answer: 
                return answer, provider["name"]
            
            if error == "429":
                print(f"[Swarm Router] {provider['name']} Rate Limited (429). Instantly hopping to next node...")
                continue 
            
            print(f"[Swarm Router] {provider['name']} Failed ({error}). Rerouting...")
            time.sleep(1)
        
        print("[Swarm Router] ALL NODES EXHAUSTED. Forcing a 10s cooldown before returning failure...")
        time.sleep(10)
        return None, "Offline"