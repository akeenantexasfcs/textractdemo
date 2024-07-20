#!/usr/bin/env python
# coding: utf-8

# In[6]:


import os
import streamlit as st
import boto3
import tempfile
import json
import botocore
import pandas as pd
from pdf2image import convert_from_bytes
from PIL import Image
import io

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
    except botocore.exceptions.ClientError:
        return False

def safe_get(dict_obj, key, default=None):
    """Safely get a value from a dictionary."""
    return dict_obj.get(key, default)

def extract_table_data(table_blocks, blocks_map):
    rows = []
    for relationship in safe_get(table_blocks, 'Relationships', []):
        if safe_get(relationship, 'Type') == 'CHILD':
            for child_id in safe_get(relationship, 'Ids', []):
                cell = blocks_map.get(child_id, {})
                if safe_get(cell, 'BlockType') == 'CELL':
                    row_index = safe_get(cell, 'RowIndex', 1) - 1
                    col_index = safe_get(cell, 'ColumnIndex', 1) - 1
                    while len(rows) <= row_index:
                        rows.append([])
                    while len(rows[row_index]) <= col_index:
                        rows[row_index].append('')
                    cell_text = safe_get(cell, 'Text', '')
                    if not cell_text:
                        for cell_relationship in safe_get(cell, 'Relationships', []):
                            if safe_get(cell_relationship, 'Type') == 'CHILD':
                                for word_id in safe_get(cell_relationship, 'Ids', []):
                                    word = blocks_map.get(word_id, {})
                                    cell_text += safe_get(word, 'Text', '') + ' '
                        cell_text = cell_text.strip()
                    rows[row_index][col_index] = cell_text
    return rows

def process_image(image_bytes, textract_client):
    response = textract_client.analyze_document(
        Document={'Bytes': image_bytes},
        FeatureTypes=['TABLES', 'FORMS']
    )
    
    extracted_text = ""
    tables = []
    form_data = {}

    blocks_map = {safe_get(block, 'Id'): block for block in safe_get(response, 'Blocks', [])}

    for block in safe_get(response, 'Blocks', []):
        block_type = safe_get(block, 'BlockType')
        if block_type == 'LINE':
            extracted_text += safe_get(block, 'Text', '') + "\n"
        elif block_type == 'TABLE':
            tables.append(extract_table_data(block, blocks_map))
        elif block_type == 'KEY_VALUE_SET' and 'KEY' in safe_get(block, 'EntityTypes', []):
            key = None
            value = None
            for relationship in safe_get(block, 'Relationships', []):
                if safe_get(relationship, 'Type') == 'VALUE':
                    for value_id in safe_get(relationship, 'Ids', []):
                        value = safe_get(blocks_map.get(value_id, {}), 'Text', '')
                elif safe_get(relationship, 'Type') == 'CHILD':
                    for child_id in safe_get(relationship, 'Ids', []):
                        key = safe_get(blocks_map.get(child_id, {}), 'Text', '')
            if key and value:
                form_data[key] = value
    
    return extracted_text, tables, form_data

def process_document(file_bytes, file_type, textract_client):
    all_text = ""
    all_tables = []
    all_form_data = {}

    if file_type == 'pdf':
        images = convert_from_bytes(file_bytes)
        for i, image in enumerate(images):
            img_byte_arr = io.BytesIO()
            image.save(img_byte_arr, format='PNG')
            img_byte_arr = img_byte_arr.getvalue()
            
            page_text, page_tables, page_form_data = process_image(img_byte_arr, textract_client)
            all_text += f"Page {i+1}:\n{page_text}\n\n"
            all_tables.extend(page_tables)
            all_form_data.update(page_form_data)
    else:  # For image files
        all_text, all_tables, all_form_data = process_image(file_bytes, textract_client)

    return all_text, all_tables, all_form_data

st.title("AWS Textract with Streamlit v8 - PDF and Image Processing")
st.write("Enter your AWS credentials and upload a PDF or image file to extract text, tables, and form data using AWS Textract.")

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
            
            extracted_text, tables, form_data = process_document(file_bytes, file_type, textract_client)
            
            st.subheader("Extracted Text:")
            st.text(extracted_text)
            
            st.subheader("Detected Tables:")
            if tables:
                for i, table in enumerate(tables):
                    st.write(f"Table {i+1}:")
                    if table:
                        df = pd.DataFrame(table)
                        st.dataframe(df)
                    else:
                        st.write("Empty table detected")
            else:
                st.write("No tables detected")
            
            st.subheader("Form Data:")
            st.json(form_data)

        except botocore.exceptions.ClientError as e:
            st.error(f"AWS Error: {str(e)}")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Please check the error message for more details.")
else:
    st.info("Please enter and confirm your AWS credentials to proceed.")

