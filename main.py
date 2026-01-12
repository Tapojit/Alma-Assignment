from fastapi import FastAPI, Depends, Body
import gradio as gr

main_app = FastAPI()


def process_documents(passport_file, g28_file):
    if passport_file is None and g28_file is None:
        return "Please upload at least one document", None, None

    # For now, just return confirmation
    passport_info = f"Passport: {passport_file}" if passport_file else "No passport uploaded"
    g28_info = f"G-28 Form: {g28_file}" if g28_file else "No G-28 form uploaded"

    status = f"✓ Files received\n{passport_info}\n{g28_info}"

    return status, None, None


with gr.Blocks(title="Alma Assignment") as interface:
    gr.Markdown("# Alma Assignment: Document Processing")
    gr.Markdown(
        "Upload passport and G-28 documents to automatically extract data and populate the form")
    with gr.Row():
        with gr.Column():
            gr.Markdown("### Upload Documents")
            passport_input = gr.File(
                label="Passport Document",
                file_types=[".pdf", ".jpg", ".jpeg", ".png"],
                type="filepath"
            )
            g28_input = gr.File(
                label="G-28 Form",
                file_types=[".pdf", ".jpg", ".jpeg", ".png"],
                type="filepath"
            )
            process_btn = gr.Button(
                "Process Documents", variant="primary", size="lg")
            clear_btn = gr.Button(
                "Clear", variant="secondary", size="lg")

        with gr.Column():
            gr.Markdown("### Results")
            status_output = gr.Textbox(
                label="Status",
                lines=3,
                interactive=False
            )
            data_output = gr.JSON(
                label="Extracted Data"
            )

    process_btn.click(
        fn=process_documents,
        inputs=[passport_input, g28_input],
        outputs=[status_output, data_output]
    )
    clear_btn.click(
        fn=lambda: (None, None, "", None),
        inputs=[],
        outputs=[passport_input, g28_input, status_output, data_output]
    )

    gr.Markdown("""
    ---
    ### Instructions:
    1. Upload a passport document (PDF or image format: JPG, PNG)
    2. Upload a G-28 form (PDF or image format: JPG, PNG)  
    3. Click "Process Documents" to extract data and populate the form
    
    **Note:** The form will be populated but NOT submitted (as per requirements)
    """)

main_app = gr.mount_gradio_app(main_app, interface, path="/")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(main_app, host="0.0.0.0", port=8000)
