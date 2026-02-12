import torch
from transformers import (
    AutoModelForCausalLM,
    AutoTokenizer,
    BitsAndBytesConfig,
)

# Local path to the model
model_path = r"C:\Users\admin\Documents\chatbot\models\llms\Qwen3-8B"

# 4-bit quantization config
bnb_config = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",          # best quality
    bnb_4bit_use_double_quant=True,     # saves memory
    bnb_4bit_compute_dtype=torch.bfloat16
)

# Load tokenizer
tokenizer = AutoTokenizer.from_pretrained(
    model_path,
    local_files_only=True
)

# Load model with 4-bit quantization
model = AutoModelForCausalLM.from_pretrained(
    model_path,
    quantization_config=bnb_config,
    device_map="auto",
    local_files_only=True
)

# Prepare prompt
prompt = "What is the future of particle accelerators?"
messages = [
    {"role": "user", "content": prompt}
]

text = tokenizer.apply_chat_template(
    messages,
    tokenize=False,
    add_generation_prompt=True,
    enable_thinking=False
)

model_inputs = tokenizer(
    [text],
    return_tensors="pt"
).to(model.device)

# Generate
generated_ids = model.generate(
    **model_inputs,
    max_new_tokens=4096
)

# Remove prompt tokens
output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()

# Parse thinking content
try:
    # Token ID for </think>
    index = len(output_ids) - output_ids[::-1].index(151668)
except ValueError:
    index = 0

thinking_content = tokenizer.decode(
    output_ids[:index],
    skip_special_tokens=True
).strip("\n")

content = tokenizer.decode(
    output_ids[index:],
    skip_special_tokens=True
).strip("\n")

print("thinking content:", thinking_content)
print("content:", content)
