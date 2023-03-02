# AUTOGENERATED! DO NOT EDIT! File to edit: ../nbs/04_data_generator.ipynb.

# %% auto 0
__all__ = ['DataGenerator']

# %% ../nbs/04_data_generator.ipynb 4
from typing import List, Callable, Tuple

import torch
import torch.nn.functional as F

from torchtyping import TensorType
from langchain import PromptTemplate

from .api import BaseAPI

# %% ../nbs/04_data_generator.ipynb 5
class DataGenerator:
    def __init__(self, config: dict, model: Callable, tokenizer: Callable, apis: List[BaseAPI],):
        start_character = config["data_generator"]["api_start_character"]
        end_character = config["data_generator"]["api_end_character"]
        output_character = config["data_generator"]["api_output_character"]
        
        # add a space, because when the model generate a token, it's also include a "space"
        self.api_start_token = tokenizer(f' {start_character}', return_tensors="pt")["input_ids"][0]
        self.api_end_token = tokenizer(end_character, return_tensors="pt")["input_ids"][0]
        self.api_output_character = tokenizer(f' {output_character}', return_tensors="pt")["input_ids"][0]
        
        self.top_k = config["data_generator"]["top_k"]
        self.sampling_threshold = config["data_generator"]["sampling_threshold"]
        self.filtering_threshold = config["data_generator"]["filtering_threshold"]
        
        self.apis = apis
        self.model = model
        self.tokenizer = tokenizer
        # TODO: handle for cases that the sentence contains ".\n\n"
        self.eos_token_id = tokenizer(".\n\n")["input_ids"][0]
    
    def _sample_api_position(
        self,
        prompt_ids: TensorType["batch_size", "seq_len"], # the ids of the prompt
    ) -> Tuple[
        TensorType["batch_size", "n_positions"], # The positions of api call
        TensorType["batch_size", "seq_len"] # The generated text
    ]:
        # TODO: add support batch
        generated_ids = prompt_ids
        api_positions = torch.tensor([])
        
        with torch.no_grad():    
            while True:
                logits = self.model(
                    input_ids=generated_ids.unsqueeze(0),
                ).logits

                last_logit = logits[0, -1, :]
                probs = torch.softmax(last_logit, dim=-1)
                
                # find the top k tokens for api call
                # TODO: add filter by larger than sampling_threshold
                top_k_tokens = torch.topk(probs, k=5, dim=-1)
                
                if self.api_start_token in top_k_tokens.indices:
                    api_position = torch.tensor([len(generated_ids)]) # the current idx
                    api_positions = torch.cat((api_positions, api_position), dim=0)
                
                # sampling a token
                # next_token = torch.multinomial(probs, num_samples=1)
                next_token = torch.argmax(probs, dim=-1)
                next_token = next_token.unsqueeze(0)
                generated_ids = torch.cat([generated_ids, next_token], dim=0)
                
                if next_token == self.eos_token_id: break
        
        return api_positions.long(), generated_ids.long()

    def _obtain_api_call(
        self,
        positions: TensorType["batch_size", "n_positions"],
        generated_ids: TensorType["batch_size", "seq_len"]
    ) -> TensorType["batch_size", "n_positions", "seq_len"]:
        MAX_PAD = 1000
        PAD_TOKEN = self.tokenizer.pad_token_id
        candidates = torch.tensor([])

        for position in positions:
            text_ids = torch.cat([generated_ids[:position], self.api_start_token])
            output = self.model.generate(
                input_ids=text_ids.unsqueeze(0),
                eos_token_id=self.eos_token_id,
                max_new_tokens=100,
            )
            
            N_PAD = MAX_PAD - output.shape[-1]
            candidates = torch.cat([
                candidates,
                F.pad(output[0], pad=(0, N_PAD), value=PAD_TOKEN).unsqueeze(0).long()
            ], dim=0)
        return candidates.long()
    
    def _sampling_api(
        self,
        positions: TensorType["batch_size", "n_positions"],
        generated_ids: TensorType["batch_size", "seq_len"],
        prompt: PromptTemplate
    ):
        for position in positions:
            for api in self.apis:
                condition_text = generated_ids[:position]
                conditioned_prompt = prompt.format(input=condition_text)
                pass
    
    def _filter_api(
        self,
        idxs: List[int]
    ):
        pass
    
    def generate(
        self,
        prompt_tempalte: PromptTemplate,
        text: str,
    ) -> List[str]:
        prompt = prompt_tempalte.format(input=text)
        prompt_ids = self.tokenizer(prompt, return_tensors="pt")["input_ids"][0]  
        # TODO: add support batch
        # sampling
        api_positions, generated_ids = self._sample_api_position(prompt_ids)
        
        # obtaining API calls
        candidates = self._obtain_api_call(api_positions, generated_ids)
        # filtering
        
        return candidates
