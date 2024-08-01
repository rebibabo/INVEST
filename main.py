from DIFF import *
from config import *
import os
from SLICE import *
import time
import json

#TODO 进度条输出，时间记录，日志记录
if __name__ == '__main__':
    logging.basicConfig(filename=LOG_PATH+'test.log', level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
    start_time = time.time()
    for software in os.listdir(DATA_PATH):
        soft_path = os.path.join(DATA_PATH,software)
        if '.DS_Store' in soft_path:continue
        for cve in os.listdir(soft_path):
            file_path = os.path.join(soft_path,cve)
            old_file_path = ''
            new_file_path = ''
            diff_path = ''
            if '.DS_Store' in file_path :continue
            for file in os.listdir(file_path):
                if 'OLD.c' in file:
                    old_file_path = os.path.join(file_path,file)
                if 'NEW.c' in file:
                    new_file_path = os.path.join(file_path,file)
                if file.endswith(".diff"):
                    diff_path = os.path.join(file_path,file)
            if old_file_path and new_file_path and diff_path:
                old_code = r'{}'.format(open(old_file_path, 'r', encoding='utf-8').read())
                new_code = r'{}'.format(open(new_file_path, 'r', encoding='utf-8').read())
                # 获取切片起始位置
                diff = DIFF('c',old_code,new_code,diff_path)
                print(diff)
                # cve_result_path = os.path.join(RESULT_PATH,software,cve)
                # if not os.path.exists(cve_result_path): os.makedirs(cve_result_path)
                if len(diff.old_cv) !=0:
                    code = old_code
                    cv_dict = diff.old_cv
                else:
                    code = new_code
                    cv_dict = diff.new_cv
                
                if len(cv_dict.keys()) == 0:
                    logging.error(f'this diff has no cv {diff_path}')
                    continue
                # 将diff中提取的关键变量记录到之前数据结果下
                diff_result_path = os.path.join(file_path,'cv.json')
                with open(diff_result_path,'w') as cv_file:
                    json.dump(diff.to_json(),cv_file)
                
                # 开始切片
                
                #     continue
                # else:
                #     slice = SLICE('c',code)
                #     slice_result_path = os.path.join(cve_result_path,'slice')
                #     slice.get_slice(cv_dict.keys(),slice_result_path)
                #     slice.pdg.see_graph(cve_result_path)
            else:
                print("mising old, new or diff file!")
                continue
    end_time = time.time()
    run_time = end_time-start_time
    print(f"Total execution time: {run_time:.2f} seconds")