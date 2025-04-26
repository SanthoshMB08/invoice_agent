import os
import json
import streamlit as st
from pymongo import MongoClient
from groq import Groq
from invoice_generator import generate_invoice_pdf
from pathlib import Path
from dotenv import load_dotenv

# ========== Environment Variables ==========
load_dotenv() 
GROQ_API_KEY = os.getenv("api_key")
mongo_uri =os.getenv("mongo_uri")
# ========== MongoDB Setup ==========
client = MongoClient(mongo_uri)
db = client['Invoice_Generator']

# Collections
customers = db['customer_data']
products = db['product_data']

# ========== Groq LLaMA Client ==========
groq_client = Groq(api_key=GROQ_API_KEY)

# ========== Streamlit Page Config ==========
st.set_page_config(page_title="AI Billing Chatbot", page_icon="🧾")
st.title("🧾 AI Billing Chatbot Assistant")

# ========== Session State Setup ==========
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []
if "pending_customers" not in st.session_state:
    st.session_state.pending_customers = None
if "last_user_input" not in st.session_state:
    st.session_state.last_user_input = ""

# ========== AI Extraction ==========
def extract_invoice_data(user_text: str):
    prompt = f"""
You are an AI assistant for generating invoices and assisting users.

Instructions:
1. If the input is a casual greeting or small talk (e.g., "hi", "hello", "how are you?"), respond with a friendly message in JSON like:
{{
  "reply": "Hi there! 😊 How can I help you today?"
}}

2. If the user gives a billing request like:
"I bought 2 strips of Augmentin and 3 Crocin for Hrishita", return:
{{
  "customer_name": "Hrishita",
  "product_names": "Augmentin, Crocin",
  "quantities": "2, 3",
  "unit_type": "strip"
}}
Respond ONLY with JSON.
User Input:
\"\"\"{user_text}\"\"\"
"""

    response = groq_client.chat.completions.create(
        model="meta-llama/llama-4-scout-17b-16e-instruct",
        messages=[
            {"role": "user", "content": prompt}
        ],
        stream=False
    )

    reply_text = response.choices[0].message.content.strip()
    try:
        return json.loads(reply_text)
    except json.JSONDecodeError:
        return {"reply": reply_text}

# ========== Mongo Data Fetch ==========
def fetch_data_from_mongo(customer_name, product_names):
    matched_customers = list(customers.find({"Name": {"$regex": customer_name, "$options": "i"}}))

    if len(matched_customers) == 1:
        customer_data = matched_customers[0]
    elif len(matched_customers) > 1:
        return {"match_customer_names": [c["Name"] for c in matched_customers]}, None
    else:
        customer_data = None

    product_list = [name.strip() for name in product_names.split(",")]
    product_data = [products.find_one({"name": {'$regex': name, '$options': 'i'}}) for name in product_list]

    return customer_data, product_data

# ========== Invoice Generator ==========
def create_invoice(customer_data, product_data_list, quantities_raw, unit_type):
    quantities = [int(q.strip()) for q in str(quantities_raw).split(",")]
    is_strip = unit_type.lower() == "strip"

    items = []
    for product, qty in zip(product_data_list, quantities):
        if not product:
            continue
        price = product["mrp"] if is_strip else product["unit_price"]
        items.append({
            "name": product["name"],
            "qty": qty,
            "rate": price,
            "total": round(qty * price, 2)
        })

    pdf_path = generate_invoice_pdf(customer_data, items)
    return pdf_path, customer_data, items



# ========== Main Chat Input ==========
user_input = st.chat_input("Type something...")

if user_input and not st.session_state.pending_customers:
    st.session_state.chat_history.append(("user", user_input))
    st.session_state.last_user_input = user_input

    with st.spinner("🤖 Thinking..."):
        try:
            extracted = extract_invoice_data(user_input)

            if "reply" in extracted:
                bot_response = extracted["reply"]

            else:
                customer_name = extracted.get("customer_name")
                product_names = extracted.get("product_names")
                quantities = extracted.get("quantities")
                unit_type = extracted.get("unit_type", "unit")

                customer_data, product_data_list = fetch_data_from_mongo(customer_name, product_names)

                if isinstance(customer_data, dict) and "match_customer_names" in customer_data:
                    bot_response = "👥 I found multiple matching customer names. Please select the correct one."
                    st.session_state.pending_customers = customer_data["match_customer_names"]
                elif customer_data is None:
                    bot_response = "⚠️ Customer not found in the database. Please check the name or add the customer first."
                else:
                    pdf_path, _, items = create_invoice(customer_data, product_data_list, quantities, unit_type)
                    item_list = "\n".join([f"{i['name']} x{i['qty']} @ ₹{i['rate']} = ₹{i['total']}" for i in items])
                    bot_response = f"🧾 *Invoice for {customer_data['Name']}*:\n\n{item_list}\n\n📄 [Download PDF]({pdf_path})"

        except Exception as e:
            bot_response = f"❌ Error: {str(e)}"

    st.session_state.chat_history.append(("bot", bot_response))
# ========== Handle Pending Customer Choice ==========
if st.session_state.pending_customers:
    st.info("Multiple customers found. Please choose one.")
    selected_name = st.selectbox("Select Customer", st.session_state.pending_customers)

    if st.button("✅ Confirm Selection"):
        extracted = extract_invoice_data(st.session_state.last_user_input)
        product_names = extracted.get("product_names")
        quantities = extracted.get("quantities")
        unit_type = extracted.get("unit_type", "unit")

        customer_data = customers.find_one({"Name": {"$regex": f"^{selected_name}$", "$options": "i"}})
        product_data_list = [products.find_one({"name": {'$regex': name.strip(), '$options': 'i'}})
                             for name in product_names.split(",")]

        pdf_path, _, items = create_invoice(customer_data, product_data_list, quantities, unit_type)
        url_safe_path = str(Path(pdf_path).as_posix())  # Converts \ to /
        item_list = "\n".join([f"{i['name']} x{i['qty']} @ ₹{i['rate']} = ₹{i['total']}" for i in items])
        bot_response = f"🧾 Invoice for *{customer_data['Name']}*:\n\n{item_list}\n\n📄 Download your invoice below."
        st.session_state.chat_history.append(("bot", bot_response))
        st.session_state.chat_history.append(("pdf", pdf_path))
        

        st.session_state.pending_customers = None
        st.session_state.last_user_input = ""
# ========== Chat History Display ==========
for role, msg in st.session_state.chat_history:
    with st.chat_message("user" if role == "user" else "assistant"):
        if role == "pdf":
            with open(msg, "rb") as f:
                st.download_button(
                    label="📥 Download Invoice PDF",
                    data=f,
                    file_name=Path(msg).name,
                    mime="application/pdf"
                )
        else:
            st.markdown(msg)

