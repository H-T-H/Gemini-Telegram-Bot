import os
import sys
import google.generativeai as genai

def list_available_models():
    """列出当前 API 密钥可以访问的所有模型"""
    try:
        # 如果命令行参数提供了 API 密钥，使用它
        if len(sys.argv) > 1:
            api_key = sys.argv[1]
            genai.configure(api_key=api_key)
        # 否则尝试从环境变量获取
        elif os.environ.get("GOOGLE_API_KEY"):
            api_key = os.environ.get("GOOGLE_API_KEY")
            genai.configure(api_key=api_key)
        else:
            print("错误：未提供 API 密钥。请通过命令行参数提供或设置 GOOGLE_API_KEY 环境变量。")
            return

        print("正在获取可用模型列表...")
        models = genai.list_models()
        
        print("\n所有可用模型:")
        print("="*50)
        
        for i, model in enumerate(models, 1):
            print(f"{i}. 名称: {model.name}")
            print(f"   显示名称: {model.display_name}")
            print(f"   支持生成: {model.supported_generation_methods}")
            print(f"   输入模态: {model.input_modalities}")
            print(f"   输出模态: {model.output_modalities}")
            print("-"*50)
        
        # 特别查找图像生成相关模型
        imagen_models = [m for m in models if 'imagen' in m.name.lower() or 'image' in str(m.output_modalities).lower()]
        if imagen_models:
            print("\n可能支持图像生成的模型:")
            print("="*50)
            for i, model in enumerate(imagen_models, 1):
                print(f"{i}. 名称: {model.name}")
                print(f"   显示名称: {model.display_name}")
                print(f"   支持生成: {model.supported_generation_methods}")
                print(f"   输入模态: {model.input_modalities}")
                print(f"   输出模态: {model.output_modalities}")
                print("-"*50)
        else:
            print("\n未找到可能支持图像生成的模型。您的 API 密钥可能没有图像生成权限。")
            
    except Exception as e:
        print(f"获取模型列表时出错: {e}")

if __name__ == "__main__":
    list_available_models() 