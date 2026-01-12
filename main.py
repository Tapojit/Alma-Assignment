from fastapi import FastAPI, Depends, Body
import gradio as gr

main_app = FastAPI()

interface = gr.Interface()

main_app = gr.mount_gradio_app(main_app, interface, path="/")
