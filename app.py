#!/usr/bin/env python
# coding: utf-8

# In[6]:


import streamlit as st
import boto3
import pandas as pd

def check_aws_credentials(access_key, secret_key, region):
    try:
        session = boto3.Session(
            aws_access_key_id=access_key,
            aws_secret_access_key=secret_key,
            region_name=region
        )
        sts = session.client('sts')
        sts.get_caller_identity()
        return True
    except Exception:
        return False

def extract_text_and_tables(response):
    text = ""
    tables = []

    for block in response['Blocks']:
        if block['BlockType'] == 'LINE':
            text += block['Text'] + "\n"
        elif block['BlockType'] == 'TABLE':
            table = []
            for relationship in block.get('Relationships', []):
                if relationship['Type'] == 'CHILD':
                    for cell_id in relationship['Ids']:
                        cell = next((item for item in response['Blocks'] if item["Id"] == cell_id), None)
                        if cell:
                            row_index = cell['RowIndex'] - 1
                            col_index = cell['ColumnIndex'] - 1
                            if len(table) <= row_index:
                                table.extend([[] for _ in range(row_index - len(table) + 1)])
                            if len(table[row_index]) <= col_index:
                                table[row_index].extend([''] * (col_index - len(table[row_index]) + 1))
                            table[row_index][col_index] = cell.get('Text', '')
            tables.append(table)

    return text, tables

def process_document(file_bytes, file_type, textract_client):
    if file_type == 'pdf':
        response = textract_client.analyze_document(
            Document={'Bytes': file_bytes},
            FeatureTypes=['TABLES', 'FORMS']
        )
    else:  # For image files
        response = textract_client.detect_document_text(
            Document={'Bytes': file_bytes}
        )
    
    return extract_text_and_tables(response)

st.title("AWS Textract with Streamlit - PDF and Image Processing")
st.write("Enter your AWS credentials and upload a PDF or image file to extract text and tables using AWS Textract.")

# AWS Credentials Input
aws_access_key = st.text_input("AWS Access Key ID", type="password")
aws_secret_key = st.text_input("AWS Secret Access Key", type="password")
aws_region = st.selectbox("AWS Region", ["us-east-2", "us-east-1", "us-west-1", "us-west-2"], index=0)

if st.button("Confirm Credentials"):
    if check_aws_credentials(aws_access_key, aws_secret_key, aws_region):
        st.success("AWS credentials are valid!")
        st.session_state.credentials_valid = True
    else:
        st.error("Invalid AWS credentials. Please check and try again.")
        st.session_state.credentials_valid = False

# File Upload (only show if credentials are valid)
if st.session_state.get('credentials_valid', False):
    uploaded_file = st.file_uploader("Choose a PDF or image file", type=["pdf", "jpg", "jpeg", "png"])

    if uploaded_file is not None:
        file_bytes = uploaded_file.read()
        file_type = uploaded_file.type.split('/')[-1]

        try:
            textract_client = boto3.client('textract',
                                           aws_access_key_id=aws_access_key,
                                           aws_secret_access_key=aws_secret_key,
                                           region_name=aws_region)
            
            extracted_text, tables = process_document(file_bytes, file_type, textract_client)
            
            st.subheader("Extracted Text:")
            st.text(extracted_text)
            
            st.subheader("Detected Tables:")
            if tables:
                for i, table in enumerate(tables):
                    st.write(f"Table {i+1}:")
                    df = pd.DataFrame(table[1:], columns=table[0] if table else [])
                    st.dataframe(df)
            else:
                st.write("No tables detected")

        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Please check the error message for more details.")
else:
    st.info("Please enter and confirm your AWS credentials to proceed.")

