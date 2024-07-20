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
                        # If 'Text' is not present, try to get it from child relationships
                        for cell_relationship in safe_get(cell, 'Relationships', []):
                            if safe_get(cell_relationship, 'Type') == 'CHILD':
                                for word_id in safe_get(cell_relationship, 'Ids', []):
                                    word = blocks_map.get(word_id, {})
                                    cell_text += safe_get(word, 'Text', '') + ' '
                        cell_text = cell_text.strip()
                    rows[row_index][col_index] = cell_text
    return rows

def process_document(image_path, textract_client):
    with open(image_path, 'rb') as document:
        image_bytes = document.read()
    
    response = textract_client.analyze_document(
        Document={'Bytes': image_bytes},
        FeatureTypes=['TABLES', 'FORMS']
    )
    
    # Save the response as a JSON file
    response_json_path = image_path + '.json'
    with open(response_json_path, 'w') as json_file:
        json.dump(response, json_file, indent=4)
    
    # Extract text, tables, and form data
    extracted_text = ""
    tables = []
    form_data = {}

    # Create a dictionary to map block IDs to blocks
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
    
    return extracted_text, tables, form_data, response_json_path, response

st.title("AWS Textract with Streamlit v7 - Detailed Debugging")
st.write("Enter your AWS credentials and upload an image to extract text, tables, and form data using AWS Textract.")

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
    uploaded_file = st.file_uploader("Choose an image file", type=["jpg", "jpeg", "png", "pdf"])

    if uploaded_file is not None:
        temp_file_path = None
        response_json_path = None
        try:
            with tempfile.NamedTemporaryFile(delete=False) as temp_file:
                temp_file.write(uploaded_file.getvalue())
                temp_file_path = temp_file.name
            
            textract_client = boto3.client('textract',
                                           aws_access_key_id=aws_access_key,
                                           aws_secret_access_key=aws_secret_key,
                                           region_name=aws_region)
            
            extracted_text, tables, form_data, response_json_path, raw_response = process_document(temp_file_path, textract_client)
            
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
            
            st.subheader("Download Full JSON Response:")
            with open(response_json_path, 'rb') as f:
                st.download_button(
                    label="Download JSON",
                    data=f,
                    file_name='textract_response.json',
                    mime='application/json'
                )

            # Debug information
            st.subheader("Debug Information:")
            st.json(raw_response)

            # Display structure of the first few blocks
            st.subheader("Structure of First Few Blocks:")
            for i, block in enumerate(raw_response.get('Blocks', [])[:5]):
                st.write(f"Block {i}:")
                st.json(block)

        except botocore.exceptions.ClientError as e:
            st.error(f"AWS Error: {str(e)}")
        except Exception as e:
            st.error(f"An error occurred: {str(e)}")
            st.error("Please check the JSON response for more details.")
        finally:
            # Clean up the temporary files
            if temp_file_path and os.path.exists(temp_file_path):
                os.unlink(temp_file_path)
            if response_json_path and os.path.exists(response_json_path):
                os.unlink(response_json_path)
else:
    st.info("Please enter and confirm your AWS credentials to proceed.")

