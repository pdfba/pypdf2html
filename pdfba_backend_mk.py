

import os
import shutil
import random
import time
import re
import fitz
import pymupdf
import configparser



# -*- coding: utf-8 -*-
from pdfminer.pdfparser import PDFParser
from pdfminer.pdfdocument import PDFDocument
from pdfminer.pdfpage import PDFPage
from pdfminer.pdfpage import PDFTextExtractionNotAllowed
from pdfminer.pdfinterp import PDFResourceManager
from pdfminer.pdfinterp import PDFPageInterpreter
from pdfminer.layout import *
from pdfminer.converter import PDFPageAggregator


from PIL import Image

from bs4 import BeautifulSoup

from openai import OpenAI
import concurrent.futures
import threading





# 定义最小尺寸阈值
MIN_WIDTH = 1
MIN_HEIGHT = 1
MAX_PAGE_PIC_NUM = 500
WORD_NUM = 5000

FILE_LOCK = threading.Lock()


# 工作目录
#WORKING_FOLDER_NAME = '/Users/liwei135/pdfba'
# 工作目录
#WORKING_FOLDER_NAME = '/home/pdfba'
# 文件夹名称
PIC_FOLDER_NAME = "docs/pdf_fig_output"
PIC_FOLDER_NAME_SHORT = "pdf_fig_output"
TXT_FOLDER_NAME = "pdf_txt_output"


def read_config(config_path, key_name):
    """
    通过正则表达式从配置文件提取 working_dir,ak等信息
    """

    #config_path_dir = f"/Users/liwei135/PycharmProjects/pdfba/{config_path}"
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



def translate(
        pdf_filename,
        session_id,

):
    #函数维度的全局变量
    ALL_PIC_X0_Y0_COORDINATE = []
    ALL_TXT_X0_Y0_COORDINATE = []
    ALL_TXT_WORDCNT = []
    ALL_INSERT_PIC_X0_Y0_COORDINATE = []
    ALL_INSERT_IMG_LOCATION = []


    # 要显示的图片列表
    show_pic_list = []
    #session_id="d3c788fd-87a8-4a96-b4b3-6fd5e1a2e095"

    WORKING_FOLDER_NAME = read_config('config.ini', 'working_dir')

    pdf_path = f"{WORKING_FOLDER_NAME}/{session_id}/{pdf_filename}"


    # 检查文件夹是否存在，如果不存在则创建
    filename = f"{WORKING_FOLDER_NAME}/{session_id}/{PIC_FOLDER_NAME}"
    if not os.path.exists(filename):
        os.makedirs(filename)
        # print(f"文件夹 '{folder_name}' 已创建。")

    # 检查文件夹是否存在，如果不存在则创建
    filename = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}"
    if not os.path.exists(filename):
        os.makedirs(filename)
        # print(f"文件夹 '{folder_name}' 已创建。")

    total_page_num = pdf_page_interpret(pdf_path, session_id)


    for page_num in range(total_page_num):
        input_file_name = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/all_element_{page_num}.txt"
        out_file_name = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/fig_only_{page_num}.txt"
        pdf_extract_fig_element(input_file_name, out_file_name)

    for page_num in range(total_page_num):
        input_file_name = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/all_element_{page_num}.txt"
        out_file_name = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/txt_only_{page_num}.txt"
        pdf_extract_txt_element(input_file_name, out_file_name)

    for page_num in range(total_page_num):
        fig_element_file_name = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/fig_only_{page_num}.txt"
        pic_x0_y0_coord = save_img_from_pdf_page(pdf_path, page_num, fig_element_file_name, session_id)
        ALL_PIC_X0_Y0_COORDINATE.append(pic_x0_y0_coord)

    # 调用函数过滤图片
    image_folder = f"{WORKING_FOLDER_NAME}/{session_id}/{PIC_FOLDER_NAME}"
    show_pic_list = delete_small_images_return_bigpic_index(image_folder, MIN_WIDTH, MIN_HEIGHT)


    for page_num in range(total_page_num):
        txt_element_file_name = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/txt_only_{page_num}.txt"
        txt_coord, txt_cnt = get_page_txtblock_wordcnt(txt_element_file_name)
        ALL_TXT_X0_Y0_COORDINATE.append(txt_coord)
        ALL_TXT_WORDCNT.append(txt_cnt)

    # 初始化二维数组
    for page_num in range(total_page_num):
        sublist = [[0, 0] for _ in range(MAX_PAGE_PIC_NUM)]
        ALL_INSERT_PIC_X0_Y0_COORDINATE.append(sublist)

    for page_pic_num in show_pic_list:
        match = re.search(r"(\d+)_(\d+)", page_pic_num)
        if match:
            page_num = int(match.group(1))
            pic_num = int(match.group(2))
            #print("page,pic:",page_num,pic_num)

            #insert_pic_x0_y0_coord = get_insert_pic_y_coordinate(pic_num, page_num)
            insert_pic_x0_y0_coord = ALL_PIC_X0_Y0_COORDINATE[page_num][pic_num]
            ALL_INSERT_PIC_X0_Y0_COORDINATE[page_num][pic_num] = insert_pic_x0_y0_coord
        else:
            print("未找到匹配的数字")

    # 初始化二维数组
    for page_num in range(total_page_num):
        location = []
        ALL_INSERT_IMG_LOCATION.append(location)

    #save_txt_with_img_tag(total_page_num, session_id)
    for page_num in range(total_page_num):
        for coord in ALL_INSERT_PIC_X0_Y0_COORDINATE[page_num]:
            if coord[1] > 0:
                # only have img, no txt
                if len(ALL_TXT_X0_Y0_COORDINATE[page_num]) == 0:
                    index = 0
                else:
                    index = find_closest_number(ALL_TXT_X0_Y0_COORDINATE[page_num], coord)

                ALL_INSERT_IMG_LOCATION[page_num].append(index)

    for page_num in range(total_page_num):
        in_file_path = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/txt_only_{page_num}.txt"
        if len(ALL_INSERT_IMG_LOCATION[page_num]) > 0:
            with open(in_file_path, "r", encoding="utf-8") as file:
                lines = file.readlines()  # 读取所有行
        else:
            continue

        pic_num = 0
        for row_num in ALL_INSERT_IMG_LOCATION[page_num]:
            line = lines[row_num].rstrip("\n")
            # print("line:",line)
            modified_line = add_http_img_tag(line, page_num, pic_num)
            # print("modified_line:",modified_line)
            lines[row_num] = modified_line
            pic_num += 1

        # 将修改后的内容写回文件
        out_file_path = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/txt_only_{page_num}_img.txt"
        with open(out_file_path, "w", encoding="utf-8") as file:
            file.writelines(lines)






    # 文件路径
    en_txt_file_path = f"{WORKING_FOLDER_NAME}/{session_id}/en_txt_only_add_img_final.txt"

    # read all txt file,remove LT content, and save to one txt file
    save_to_one_txt(total_page_num, en_txt_file_path, session_id)

    # 将英文中的#替换为空格，去掉页码
    en_txt_file_path_2 = f"{WORKING_FOLDER_NAME}/{session_id}/en_txt_only_add_img_final_2.txt"
    modify_en_txt_format(en_txt_file_path, en_txt_file_path_2)

    output_txt_file_1 = f"{WORKING_FOLDER_NAME}/{session_id}/docs/index_0.md"
    translate_by_ai_agent_save_file(en_txt_file_path_2, output_txt_file_1)

    # 读取文件，解决一下#前面无换行的问题
    output_txt_file_2 = f"{WORKING_FOLDER_NAME}/{session_id}/docs/index.md"
    modify_txt_format(output_txt_file_1, output_txt_file_2)



    # 要删除的文件列表
    files_to_delete = [f"{WORKING_FOLDER_NAME}/{session_id}/translate_to_cn_2.txt",
                       f"{WORKING_FOLDER_NAME}/{session_id}/en_txt_only_add_img_final_2.txt",
                       f"{WORKING_FOLDER_NAME}/{session_id}/en_txt_only_add_img_final.txt",
                       f"{WORKING_FOLDER_NAME}/{session_id}/translate_to_cn_1.txt",
                       f"{WORKING_FOLDER_NAME}/{session_id}/translate_1.html",
                       f"{WORKING_FOLDER_NAME}/{session_id}/translate_2.html",
                       f"{WORKING_FOLDER_NAME}/{session_id}/translate_3.html",
                       f"{WORKING_FOLDER_NAME}/{session_id}/translate_4.html",
                       f"{WORKING_FOLDER_NAME}/{session_id}/translate_5.html"]

    # 遍历文件列表并删除
    for file_name in files_to_delete:
        if os.path.exists(file_name):  # 检查文件是否存在
            os.remove(file_name)  # 删除文件
            #print(f"文件 {file_name} 已删除")
        else:
            print(f"文件 {file_name} 不存在")

    # 要删除的目录
    dir_txt_path = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}"
    try:
        shutil.rmtree(dir_txt_path)
        #print(f"目录 {dir_txt_path} 及其所有内容已删除")
    except OSError as e:
        print(f"删除失败: {e}")

    # 配置端口，这块代码有问题，临时这么用一下。后续应保障端口不重复
    PORT = random.randint(9000, 65000)

    pdf_name = pdf_filename.rsplit(".", 1)[0]

    html_link = f"[{session_id}/{pdf_name}.html](http://pdfba.com:8080/{session_id}_h/)"
    #print("html_str:", html_link)

    return html_link


def pdf_page_interpret(pdf_path, session_id):
    # 逐页解析pdf所有元素，并保存到txt文件，返回总页数

    file_name_all_txt = ""
    page_num = 0

    WORKING_FOLDER_NAME = read_config('config.ini', 'working_dir')

    # os.chdir(r'F:\test')
    fp = open(pdf_path, 'rb')

    # 来创建一个pdf文档分析器
    parser = PDFParser(fp)
    # 创建一个PDF文档对象存储文档结构
    document = PDFDocument(parser)
    # 检查文件是否允许文本提取
    if not document.is_extractable:
        # print("123")
        raise PDFTextExtractionNotAllowed
    else:
        # 创建一个PDF资源管理器对象来存储资源
        rsrcmgr = PDFResourceManager()

        # 创建 LAParams 对象并调整参数
        laparams = LAParams(
            line_overlap=0.5,
            char_margin=2.0,
            line_margin=0.5,
            word_margin=0.1,
            boxes_flow=0.5,
            detect_vertical=False,  # 禁用垂直文本检测
            all_texts=False,  # 仅解析可见文本
        )

        device = PDFPageAggregator(rsrcmgr, laparams=laparams)
        # 创建一个PDF解释器对象
        interpreter = PDFPageInterpreter(rsrcmgr, device)
        # 处理每一页

        for page in PDFPage.create_pages(document):
            # print("page:",page_num)
            # #start_time = time.time()

            interpreter.process_page(page)

            # 记录结束时间
            #end_time = time.time()
            # 计算并打印执行时间
            #execution_time = end_time - start_time
            #print(f"函数执行时间1: {execution_time:.4f} 秒")

            #start_time = time.time()

            file_name_all_txt = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/all_element_{page_num}.txt"

            # 接受该页面的LTPage对象
            layout = device.get_result()
            for x in layout:
                # 记录开始时间
                with open(file_name_all_txt, 'a') as file_all:
                    print(x, file=file_all)

            # 记录结束时间
            #end_time = time.time()
            # 计算并打印执行时间
            #execution_time = end_time - start_time
            # print(f"函数执行时间2: {execution_time:.4f} 秒")

            page_num = page_num + 1

    # print("total page: ",page_num)
    return page_num


def pdf_extract_fig_element(input_file, output_file):
    # 正则表达式匹配 <LTFigure> 行
    pattern = r"<LTFigure\(Im[^>]+>"

    # 打开输入文件并读取内容
    with open(input_file, "r", encoding="utf-8") as file:
        content = file.readlines()

    # 提取所有 <LTFigure> 行
    ltfigure_lines = [line.strip() for line in content if re.match(pattern, line)]

    # 将提取的内容写入输出文件
    with open(output_file, "w", encoding="utf-8") as file:
        for line in ltfigure_lines:
            file.write(line + "\n")

    # print(f"已提取 {len(ltfigure_lines)} 行 <LTFigure> 内容到 {output_file}")


def pdf_extract_txt_element(input_file, output_file):
    # 正则表达式匹配 <LTFigure> 行
    pattern = r"<LTTextBox[^>]+>"

    # 打开输入文件并读取内容
    with open(input_file, "r", encoding="utf-8") as file:
        content = file.readlines()

    # 提取所有 <LTFigure> 行
    lttxtbox_lines = [line.strip() for line in content if re.match(pattern, line)]

    # 将提取的内容写入输出文件
    with open(output_file, "w", encoding="utf-8") as file:
        for line in lttxtbox_lines:
            file.write(line + "\n")

    # print(f"已提取 {len(lttxtbox_lines)} 行 <LTTextBox> 内容到 {output_file}")


def save_img_from_pdf_page(pdf_file_path, page_num, fig_element_file_name, session_id):
    # 文件路径
    file_path = fig_element_file_name

    WORKING_FOLDER_NAME = read_config('config.ini', 'working_dir')

    # 打开文件并读取所有行
    with open(file_path, "r", encoding="utf-8") as file:
        lines = file.readlines()

    # 去除每行的换行符，并将结果存储到列表中
    data_list = [line.strip() for line in lines]

    pattern = r"(\d+\.\d+,\d+\.\d+,\d+\.\d+,\d+\.\d+)\s+matrix="

    fig_coord = []

    for line_data in data_list:
        match = re.search(pattern, line_data)
        # 检查是否匹配成功
        if match:
            fig_coord.append(match.group(1))
            # print("提取的内容:", match.group(1))

    # 用于存储图片坐标
    fig_x0_y0_coord = []

    # 遍历 fig_coord 列表中的每个字符串
    for coord in fig_coord:
        # 按逗号分割字符串
        parts = coord.split(',')
        # 提取最后一个数字并转换为浮点数（或整数，根据需要）
        x0_y0 = [float(parts[0]), float(parts[1])]
        # 将最后一个数字添加到 last_numbers 列表中
        fig_x0_y0_coord.append(x0_y0)

    # print("fig_y_coord:",fig_y_coord)

    # 打开 PDF 文件
    pdf_path = pdf_file_path
    doc = fitz.open(pdf_path)

    page = doc.load_page(page_num)
    ptm = page.transformation_matrix
    # print(ptm)
    ind = 0
    for coord_data in fig_coord:
        # PDF 坐标系统中的边界框
        x0_pdf, y0_pdf, x1_pdf, y1_pdf = map(float, coord_data.split(","))
        rect = pymupdf.Rect(x0_pdf, y0_pdf, x1_pdf, y1_pdf) * ~ptm
        # print(rect)
        # 渲染指定区域为图片
        pix = page.get_pixmap(clip=rect, dpi=300)
        fig_file_name = f"{WORKING_FOLDER_NAME}/{session_id}/{PIC_FOLDER_NAME}/fig_{page_num}_{ind}.png"
        # print(fig_file_name)
        pix.save(fig_file_name)
        # print("Saved figure as ",fig_file_name)
        ind = ind + 1

    return fig_x0_y0_coord


# 过滤小图片的函数
def delete_small_images_return_bigpic_index(folder_path, min_width, min_height):
    filtered_images = []
    big_pic_list = []

    for filename in os.listdir(folder_path):
        if filename.lower().endswith(".png"):  # 只处理 PNG 文件
            file_path = os.path.join(folder_path, filename)
            # print(file_path)
            try:
                with Image.open(file_path) as img:
                    width, height = img.size
                    if width >= min_width or height >= min_height:
                        # print(f"大图片: {filename} ({width}x{height})")
                        # 使用正则表达式提取 _ 和 . 之间的数字
                        match = re.search(r"fig_(\d+_\d+)\.", filename)
                        if match:
                            number = match.group(1)  # 提取匹配的数字部分
                            big_pic_list.append(number)
                            # print("提取的数字:", number)

                        else:
                            print("未找到匹配的数字")
                    else:
                        filtered_images.append(file_path)

            except Exception as e:
                print(f"无法读取图片 {filename}: {e}")

    # 遍历列表并删除文件或文件夹
    for path in filtered_images:
        try:
            os.remove(path)
            print(f"已删除文件: {path}")
        except OSError as e:
            print(f"删除 {path} 失败: {e}")

    return big_pic_list


# 获取文本字数
def get_page_txtblock_wordcnt(page_file_path):
    # 文件路径
    file_path = page_file_path

    # 用于保存提取的数字部分
    txt_coord_x0_y0_list = []
    word_count_list = []
    total_txt_len = 0

    # 逐行读取文件
    with open(file_path, "r", encoding="utf-8") as file:
        for line in file:
            # 使用正则表达式提取数字部分
            match = re.search(r"(\d+\.\d+),(\d+\.\d+),(\d+\.\d+),(\d+\.\d+)", line)
            if match:
                # 将提取的数字部分保存到列表
                x0_y0_list = [match.group(1), match.group(2)]
                txt_coord_x0_y0_list.append(x0_y0_list)

            # 使用正则表达式提取单引号内的字符串
            match = re.search(r",(\d+\.\d+)\s+(.*?)>", line)
            if match:
                # 将提取的字符串保存到列表
                text = match.group(2)
                # print(text)
                text_len = len(text.split())
                total_txt_len = total_txt_len + text_len
                word_count_list.append(total_txt_len)

    # 打印结果
    return txt_coord_x0_y0_list, word_count_list


# 获取每页待插入img的y坐标，较全量的是过滤掉了小img
#def get_insert_pic_y_coordinate(pic_num, pageno):
#    x0_y0_coord = ALL_PIC_X0_Y0_COORDINATE[pageno][pic_num]
#    return x0_y0_coord


def find_closest_number(lst, target):
    # 初始化最小差异为一个较大的值
    min_diff = float('inf')
    # 初始化最接近的数字和下标
    closest_number = None
    closest_index = -1

    target_x0 = float(target[0])
    target_y0 = float(target[1])

    # 遍历列表
    for index, x0_y0 in enumerate(lst):
        # 计算当前数字与目标数字的差异
        number_x0 = float(x0_y0[0])
        number_y0 = float(x0_y0[1])
        # 对于双列PDF, 只比较同一列情况
        if 150 > abs(number_x0 - target_x0):
            diff = abs(number_y0 - target_y0)
            # 如果当前差异小于最小差异，则更新最小差异、最接近的数字和下标
            if diff < min_diff:
                min_diff = diff
                closest_number = number_y0
                closest_index = index

    return closest_index


def add_http_img_tag(text, page_num, img_num):
    # 构造图片路径
    img_path = f"  <p><img src={PIC_FOLDER_NAME_SHORT}/fig_{page_num}_{img_num}.png></p>"

    if text.endswith("\">"):
        return text.replace("\\n\">", f"{img_path}\\n\">\n")
    elif text.endswith("\'>"):
        return text.replace("\\n\'>", f"{img_path}\\n\'>\n")
    else:
        return "wrong"  # 如果没有匹配的结尾，返回原字符串


def save_to_one_txt(total_page_num, txt_file_path, session_id):
    # 用于保存提取的内容
    extracted_texts = []
    WORKING_FOLDER_NAME = read_config('config.ini', 'working_dir')

    for page_num in range(total_page_num):
        in_file_path = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/txt_only_{page_num}_img.txt"

        # 判断文件是否存在
        if not os.path.exists(in_file_path):
            in_file_path = f"{WORKING_FOLDER_NAME}/{session_id}/{TXT_FOLDER_NAME}/txt_only_{page_num}.txt"

        with open(in_file_path, "r", encoding="utf-8") as file:
            lines = file.readlines()  # 读取所有行

        # 分离左侧和右侧页面数据
        left_pages = []
        right_pages = []

        for line in lines:
            # 使用正则表达式提取第一个坐标数字
            match = re.search(r'<LTTextBoxHorizontal\(\d+\)\s+([\d.]+)', line)
            if match:
                x_coord = float(match.group(1))
                if x_coord < 300:
                    left_pages.append(line)
                else:
                    right_pages.append(line)

        # 合并结果：左侧在前，右侧在后
        sorted_data = left_pages + right_pages


        # 逐行读取文件
        for line in sorted_data:
            # 使用正则表达式提取 ' \n' 或 " \n" 之间的内容
            match = re.search(r"['\"](.*?)\\n['\"]", line)
            if match:
                extracted_texts.append(match.group(1))

    # 将修改后的内容写到一个文件
    with open(txt_file_path, "w", encoding="utf-8") as file:
        for line in extracted_texts:
            file.write(line + '\n')





def translate_by_ai_agent_save_file(en_file_path, cn_file_path):

    # 定义锁和结果列表

    TRANSLATE_RESULTS = []


    ak = read_config('config.ini', 'ak')

    #client = OpenAI(api_key=ak, base_url="https://api.deepseek.com")
    client = OpenAI(api_key=ak, base_url="https://xiaoai.plus/v1")

    prompt="""请将英文内容翻译成中文。
    请严格遵循如下指令：
    1.内容是科技论文，需要注意翻译的准确性和严谨性。
    2.容是从PDF中提取出来的，有些内容会出现上下行的乱序，特别是目录部分，会出现....和数字的乱排，可以尝试恢复格式。
    3.不要翻译也不要删除html标签相关的内容，html标签会以<p><img src=pdf_fig_output开头。
    4.尝试让输出内容可读性好一些，比如一些内容识别为表格形式的数据，最好用表格展示出来。
    5.如果输出的内容存在一个#或多个#,在第一个#前面一定一定要加上换行符。
    6.如果识别出来是表格内容，但无法完整的恢复成markdown格式的表格，就不要翻译。
    7.输出中的表格的描述，不要作为markdown的标题，前面不要加#，表格描述的末尾要要加两个空格一个换行，以使得markdown表格可以正常显示。
    8.token和tokens是专有名词，不需要翻译。
    """



    # 初始化一个空列表，用于存储每次读取的内容
    file_path = en_file_path
    file_path_trans = cn_file_path




    # 打开文件并读取内容
    content_list = []
    cnt = 0
    with open(file_path, "r", encoding="utf-8") as file:
        while True:
            # 每次读取 WORD_NUM 个字符
            chunk = file.read(WORD_NUM)
            print("read:", cnt)
            cnt += 1
            if not chunk:  # 如果读取不到内容，说明文件已读完
                break
            # 将读取的内容添加到列表中
            content_list.append(chunk)

    # 定义处理每个 chunk 的函数
    def process_chunk(client, chunk, i, prompt):


        response = client.chat.completions.create(
            # model="deepseek-r1",
            #model="deepseek-chat",
            model="deepseek-v3",
            max_tokens=8000,  # 最大输出8K
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": chunk},
            ],
            stream=False
        )
        print("query:", i)
        # print(response.choices[0].message.content)
        with FILE_LOCK:
            TRANSLATE_RESULTS.append((i, response.choices[0].message.content))  # 将结果按顺序存储到列表中


    # 使用 ThreadPoolExecutor 并行处理每个 chunk
    with concurrent.futures.ThreadPoolExecutor() as executor:
        futures = []
        for i, chunk in enumerate(content_list):
            # 提交任务到线程池
            future = executor.submit(process_chunk, client, chunk, i, prompt)
            futures.append(future)
            print(f"任务 {i} 已提交，等待 1 秒...")
            time.sleep(1)  # 每个任务间隔 1 秒

        # 等待所有任务完成
        concurrent.futures.wait(futures)

    # 按顺序写入文件
    with open(file_path_trans, "w", encoding="utf-8") as file:
        for i, result in sorted(TRANSLATE_RESULTS, key=lambda x: x[0]):  # 按索引排序
            file.write(result)

    print("所有任务已完成")




def set_html_img_auto_adjust(input_html_file, output_html_file):
    # 读取 HTML 文件
    with open(input_html_file, "r", encoding="utf-8") as file:
        html_content = file.read()

    # 使用 BeautifulSoup 解析 HTML
    soup = BeautifulSoup(html_content, "html.parser")

    # 找到所有的 <img> 标签
    for img_tag in soup.find_all("img"):
        # 添加自适应样式
        img_tag["style"] = "max-width: 100%; height: auto;"

    # 将修改后的内容写回文件
    with open(output_html_file, "w", encoding="utf-8") as file:
        file.write(str(soup))

    print("HTML 文件已修改并保存为", output_html_file)




def modify_en_txt_format(input_txt_file, output_txt_file):
    with open(input_txt_file, "r", encoding="utf-8") as infile, open(output_txt_file, "w", encoding="utf-8") as outfile:
        for line in infile:
            new_line = line.replace("#", " ")
            stripped_line = new_line.strip()
            if stripped_line.isdigit() and len(stripped_line) > 0:
                outfile.write(" \n")
            else:
                outfile.write(new_line)

    #print(f"TXT 文件已修改并保存为: {output_txt_file}")


def modify_txt_format(input_txt_file, output_txt_file):

    with open(input_txt_file, "r", encoding="utf-8") as file:
        content = file.read()


    # 把句号换成句号加换行，句号后已经有换行的除外
    modified_content_1 = re.sub(r'([。；])(?!\n)', r'\1  \n', content)

    # 给换行前面加两个空格
    modified_content_2 = re.sub(r'(\n)', r'  \n', modified_content_1)

    # 让mkdocs能正常显示表格
    modified_content_3 = re.sub(r'(^表.+?\n)', r'\1\n', modified_content_2, flags=re.MULTILINE)

    # 将修改后的内容保存到新文件
    with open(output_txt_file, "w", encoding="utf-8") as file:
        file.write(modified_content_3)

    print(f"TXT 文件已修改并保存为: {output_txt_file}")



