
import os
import gradio as gr
from scanf import scanf
import shutil
import subprocess
import yaml
import uuid
import re


from pdfba_backend_mk import translate

from concurrent.futures import ThreadPoolExecutor
# 创建线程池（最大50线程）
executor = ThreadPoolExecutor(max_workers=50)



def immediate_response(file_type, file_input):
    """立即返回空响应"""
    return "正在处理中，请稍后"

def process_result(future):
    """处理Future对象获取结果"""
    try:
        return future.result()
    except Exception as e:
        return f"错误: {str(e)}"

def read_config(config_path, key_name):
    """
    通过正则表达式从配置文件提取 working_dir,ak等信息
    """
    #config_path_dir = f"/Users/liwei135/pdfba/{config_path}"
    config_path_dir = f"/home/pdfba/{config_path}"



    with open(config_path_dir, 'r') as f:
        config_text = f.read()

    # 匹配 working_dir 的值（支持等号或冒号分隔）
    match = re.search(
        rf'^{key_name}\s*[=:]\s*(.*?)\s*$',
        config_text,
        re.MULTILINE
    )

    if not match:
        raise ValueError(f"{key_name} not found in config file")

    # 去除可能的引号并处理路径
    result = match.group(1).strip('\'"')

    return result

# The following variables associate strings with specific languages
lang_map = {
    "Simplified Chinese": "zh",
    "English": "en",
}

def submit_task(file_type,file_input):
    """提交任务到线程池"""
    #print("提交任务到线程池")
    future = executor.submit(translate_file, file_type, file_input)

    return future
    #return future.result()

def run_mkdoc_server(html_link):
    # get  port from html_link
    # 提取 session_id 和 PORT
    # html_link的格式"[6049b15f-e9a7-43b0-b3cf-7b4834230df7/MapReduce.html](http://127.0.0.1:13988/translated_html/MapReduce.html)"

    #print("run_mkdoc_server html_link:", html_link)

    result = scanf("[%s/%s](%s:%d/%s)", html_link)

    if result:
        session_id = result[0]
        port = result[3]
    else:
        print("未匹配到session_id,port")
        return
    WORKING_FOLDER_NAME=read_config('config.ini','working_dir')

    print(WORKING_FOLDER_NAME)

    dir_name = f"{WORKING_FOLDER_NAME}/{session_id}"
    # 切换到工作 目录
    os.chdir(dir_name)

    # 定义配置内容（Python 字典格式）
    config = {
        "site_name": " ",
        "nav": [
            {"首页": "index.md"}
        ]
    }

    # 写入 YAML 文件
    with open("mkdocs.yml", "w", encoding="utf-8") as f:
        yaml.dump(config, f, allow_unicode=True, sort_keys=False)  # allow_unicode 支持中文

    print("mkdocs.yml 已生成！")

    try:
        """
        # 使用 subprocess.Popen 启动 MkDocs 服务器（非阻塞方式）
        process = subprocess.Popen(
            ["mkdocs", "serve", "--dev-addr", f"0.0.0.0:{port}"],
            cwd=dir_name,
            text=True
        )
        print(f"MkDocs 服务器已启动，访问地址：http://0.0.0.0:{port}")
        """
        output_dir = f"{WORKING_FOLDER_NAME}/{session_id}_h"
        process = subprocess.Popen(
            ["mkdocs", "build", "--site-dir", output_dir],
            cwd=dir_name,  # 在指定目录执行
            text=True
        )
        print(f"{process}MkDocs 已经完成index.html的生成")

    except FileNotFoundError:
        print("错误：未找到 mkdocs 命令，请确保 MkDocs 已安装。")





def translate_file(
        file_type,
        file_input

):
    """
    This function translates a PDF file from one language to another.

    Inputs:
        - file_type: The type of file to translate
        - file_input: The file to translate
        - link_input: The link to the file to translate

    Returns:
        - output_html_link： html linkThe translated file
    """

    session_id = uuid.uuid4()
    #session_id="d3c788fd-87a8-4a96-b4b3-6fd5e1a2e095"

    WORKING_FOLDER_NAME = read_config('config.ini', 'working_dir')
    print(WORKING_FOLDER_NAME)

    # 基于session_id生成一个本地文件夹，这块不太合理，后续应该基于user id生成一个文件夹
    os.chdir(WORKING_FOLDER_NAME)

    working_dir = f"{WORKING_FOLDER_NAME}"
    output = f"{session_id}"

    if not os.path.exists(working_dir):
        os.makedirs(working_dir)
        print(f"文件夹 '{working_dir}' 已创建。")

    if not os.path.exists(output):
        os.makedirs(output)
        print(f"文件夹 '{output}' 已创建。")

    output_dir = f"{WORKING_FOLDER_NAME}/{session_id}"

    os.chdir(output_dir)

    if file_type == "File":
        if not file_input:
            raise gr.Error("No input")
        file_path = shutil.copy(file_input, output_dir)

    filename = os.path.basename(str(file_input))
    print("filename:", filename)

    file_raw = f"{output}/{filename}"

    lang_from = "English"
    lang_to = "Chinese"

    #print(f"Files before translation: {file_raw}")

    output_html_link = translate(str(filename), session_id)

    #print(f"Files after translation: {output_html_link}")
    run_mkdoc_server(output_html_link)

    return output_html_link


# Global setup
custom_blue = gr.themes.Color(
    c50="#E8F3FF",
    c100="#BEDAFF",
    c200="#94BFFF",
    c300="#6AA1FF",
    c400="#4080FF",
    c500="#165DFF",  # Primary color
    c600="#0E42D2",
    c700="#0A2BA6",
    c800="#061D79",
    c900="#03114D",
    c950="#020B33",
)

custom_css = """
    .secondary-text {color: #999 !important;}
    footer {visibility: hidden}
    .env-warning {color: #dd5500 !important;}
    .env-success {color: #559900 !important;}

    /* Add dashed border to input-file class */
    .input-file {
        border: 1.2px dashed #165DFF !important;
        border-radius: 6px !important;
    }

    .progress-bar-wrap {
        border-radius: 8px !important;
    }

    .progress-bar {
        border-radius: 8px !important;
    }

    .pdf-canvas canvas {
        width: 100%;
    }
    """

tech_details_string = f"""
                    - pdfba.com: 科技论文大模型翻译<br>
                    - 联系方式: 50558525@qq.com<br>
                """

# The following code creates the GUI
with gr.Blocks(
        title="PDFBA.COM",
        theme=gr.themes.Default(
            primary_hue=custom_blue, spacing_size="md", radius_size="lg"
        ),
        css=custom_css,

) as pdfba_ui:
    with gr.Row():
        with gr.Column(scale=1):
            gr.Markdown("## 待翻译的PDF文件")
            file_type = gr.Radio(
                choices=["File"],
                label="Type",
                value="File",
                visible=False,
            )
            file_input = gr.File(
                label="File",
                file_count="single",
                file_types=[".pdf"],
                type="filepath",
                elem_classes=["input-file"],
            )


            def on_select_filetype(file_type):
                return (
                    gr.update(visible=file_type == "File"),

                )


            translate_btn = gr.Button("Translate", variant="primary")

            tech_details_tog = gr.Markdown(
                tech_details_string
            )

            file_type.select(
                on_select_filetype,
                file_type,
                [file_input],

            )

        with gr.Column(scale=2):
            gr.Markdown("## 翻译结果")

            gr.Markdown("翻译需要3-5分钟，翻译完成后会生成可访问的HTML链接，请不要刷新界面。")
            FE_OUTPUT_HTML_LINK = gr.Markdown("HTML Link:")

    # Event handlers
    file_input.upload(
        lambda x: x,
        inputs=file_input,

    )

    future_state = gr.State()  # 用于存储Future对象

    translate_btn.click(
        fn=immediate_response,
        inputs=[
            file_type,
            file_input
        ],
        outputs=FE_OUTPUT_HTML_LINK
    ).then(
        fn=submit_task,
        inputs=[file_type, file_input],
        outputs=future_state
    ).then(
        fn=process_result,
        inputs=[future_state],  # 接收上一步的输出
        outputs=FE_OUTPUT_HTML_LINK
)


def setup_gui(
        share: bool = False, server_port=80
) -> None:
    """
    Setup the GUI with the given parameters.

    Inputs:
        - share: Whether to share the GUI.
        - auth_file: The file path to read the user name and password.

    Outputs:
        - None
    """

    try:
        pdfba_ui.queue(default_concurrency_limit=50)
        pdfba_ui.launch(
            server_name="0.0.0.0",
            debug=False,
            inbrowser=True,
            share=share,
            server_port=server_port,
        )
    except Exception:
        print(
            "Error launching GUI using 0.0.0.0.\nThis may be caused by global mode of proxy software."
        )
        print(f"启动失败: {str(Exception)}")


# For auto-reloading while developing
if __name__ == "__main__":
    setup_gui()
