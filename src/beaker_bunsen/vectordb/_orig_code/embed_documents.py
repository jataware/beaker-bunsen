# -*- coding: utf-8 -*-

import glob
import logging
from .embed_utils import RecursiveCharacterTextSplitter,count_words,start_chromadb
logger = logging.getLogger(__name__)
#TODO: add openai embedder, esp for code..
#TODO: add rst splitter from elsewhere?
def embed_documents(documentation_dir,collection_name="documentation_index",top_k=5):
        collection = start_chromadb(collection_name=collection_name)
        #get docs
        documents=glob.glob(documentation_dir+'/**',recursive=True)
        documents_to_add=[]
        for file_path in documents:
            if '.rst' in file_path or '.md' in file_path:
                with open(file_path, 'r') as file:
                    file_content = file.read()
                documents_to_add.append((file_content,{'source':file_path}))
        
        #check if already there
        metadatas=collection.get()['metadatas']
        sources=[metadata['source'] for metadata in metadatas]
        docs=[doc for doc in documents_to_add if doc[1] not in sources] 
        
        #chunk documentation
        chunk_size=300
        text_splitter = RecursiveCharacterTextSplitter(chunk_size = chunk_size, chunk_overlap = 0,length_function=count_words,separators=["\n\n", "\n", " "])
        documents_to_add = text_splitter.split_documents(documents_to_add)
        
        #realign doc content for input into chroma
        document_texts=[doc[0] for doc in documents_to_add]
        metadatas=[doc[1] for doc in documents_to_add]
        ids=[metadata['source']+'_'+metadata['chunk_number'] for metadata in metadatas]
        
        # Add to ChromaDB collection
        collection.add(
            documents=document_texts,
            metadatas=metadatas,
            ids=ids
        )

def query_docs(query,collection_name="documentation_index",path="/bio_context/chromadb_functions",n_results=5):
    collection = start_chromadb(collection_name=collection_name,path=path)
    result = collection.query(
        query_texts=[query],
        n_results=n_results
    )
    text=''
    for i in range(len(result['ids'][0])):
        text+=f"Documentation from {result['ids'][0][i]} :\n{result['documents'][0][i]}"

    return text
