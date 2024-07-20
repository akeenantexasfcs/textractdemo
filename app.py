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

def extract_table_data(table_blocks, blocks_map):
    rows = []
    for relationship in table_blocks['Relationships']:
        if relationship['Type'] == 'CHILD':
            for child_id in relationship['Ids']:
                cell = blocks_map[child_id]
                if cell['BlockType'] == 'CELL':
                    row_index = cell['RowIndex']
                    col_index = cell['ColumnIndex']
                    if len(rows) < row_index:
                        # Add a new row
                        rows.append([])
                    # Pad the row with empty strings if needed
                    while len(rows[row_index-1]) < col_index:
                        rows[row_index-1].append('')
                    if cell['Text']:
                        rows[row_index-1].append(cell['Text'])
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
    blocks_map = {block['Id']: block for block in response['Blocks']}

    for block in response['Blocks']:
        if block['BlockType'] == 'LINE':
            extracted_text += block['Text'] + "\n"
        elif block['BlockType'] == 'TABLE':
            tables.append(extract_table_data(block, blocks_map))
        elif block['BlockType'] == 'KEY_VALUE_SET' and 'KEY' in block['EntityTypes']:
            key = None
            value = None
            for relationship in block['Relationships']:
                if relationship['Type'] == 'VALUE':
                    for value_id in relationship['Ids']:
                        value = blocks_map[value_id]['Text']
                elif relationship['Type'] == 'CHILD':
                    for child_id in relationship['Ids']:
                        key = blocks_map[child_id]['Text']
            if key and value:
                form_data[key] = value
    
    return extracted_text, tables, form_data, response_json_path

st.title("AWS Textract with Streamlit v5 - Robust Table Detection")
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
            
            extracted_text, tables, form_data, response_json_path = process_document(temp_file_path, textract_client)
            
            st.subheader("Extracted Text:")
            st.text(extracted_text)
            
            st.subheader("Detected Tables:")
            if tables:
                for i, table in enumerate(tables):
                    st.write(f"Table {i+1}:")
                    if table:
                        df = pd.DataFrame(table[1:], columns=table[0] if table[0] else [f"Column {j+1}" for j in range(len(table[1]))])
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

