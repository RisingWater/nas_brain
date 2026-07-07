# wxauto.py
import requests
import sys
import os
import logging
import base64
from src.common.utils import cfg
from typing import Dict, Any

logger = logging.getLogger(__name__)

class WXAuto:
    def __init__(self):
        self._api_url = cfg.WXAUTO_API_URL
        self._token = cfg.WXAUTO_API_TOKEN

    def is_valid(self) -> bool:
        """
        Check if the WXAuto API is valid
        """
        return self._api_url is not None and self._token is not None
    
    def send_text_message(self, who, msg, wxname="", exact=False, clear=True, at=""):
        """
        Send text message via WXAuto API
        
        Args:
            who (str): Recipient name (e.g., "文件传输助手")
            msg (str): Message content to send
            wxname (str): WeChat name (optional)
            exact (bool): Whether to match recipient exactly
            clear (bool): Whether to clear input after sending
            at (str): @ someone (optional)
            
        Returns:
            dict: API response
        """
        if not self._api_url or not self._token:
            error_msg = "WXAuto API URL or Token not configured"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        try:
            url = f"{self._api_url}/v1/wechat/send"
            
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {self._token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "wxname": wxname,
                "who": who,
                "exact": exact,
                "msg": msg,
                "clear": clear,
                "at": at
            }
            
            logger.info(f"Sending message to '{who}': {msg[:50]}...")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"Message sent successfully to '{who}'")
                return {"success": True, "data": result}
            else:
                error_msg = f"API request failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg, "status_code": response.status_code}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
    def get_next_new_message(self, wxname="", filter_mute=False, timeout=30):
        """
        Get next new message via WXAuto API
        
        Args:
            wxname (str): WeChat name (optional)
            filter_mute (bool): Whether to filter muted chats
            
        Returns:
            dict: API response with message data
        """
        if not self._api_url or not self._token:
            error_msg = "WXAuto API URL or Token not configured"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        try:
            url = f"{self._api_url}/v1/wechat/getnextnewmessage"
            
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {self._token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "wxname": wxname,
                "filter_mute": filter_mute
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=timeout)
            
            if response.status_code == 200:
                result = response.json()
                
                if result.get("success"):
                    message_data = result.get("data", {})
                    messages = message_data.get("msg", [])
                    
                    if messages:
                        logger.info(f"Received new message from '{message_data.get('chat_name', 'Unknown')}'")
                        return {
                            "success": True,
                            "has_message": True,
                            "chat_name": message_data.get("chat_name"),
                            "chat_type": message_data.get("chat_type"),
                            "messages": messages,
                            "raw_data": result
                        }
                    else:
                        return {
                            "success": True,
                            "has_message": False,
                            "raw_data": result
                        }
                else:
                    error_msg = result.get("message", "Unknown error")
                    logger.error(f"API returned error: {error_msg}")
                    return {
                        "success": False,
                        "error": error_msg,
                        "raw_data": result
                    }
            else:
                error_msg = f"API request failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg, "status_code": response.status_code}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def upload_file(self, file_path, description="", uploader=""):
        """
        Upload file via WXAuto API
        
        Args:
            file_path (str): Path to the file to upload
            description (str): File description (optional)
            uploader (str): Uploader name (optional)
            
        Returns:
            dict: API response with file_id
        """
        if not self._api_url or not self._token:
            error_msg = "WXAuto API URL or Token not configured"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        if not os.path.exists(file_path):
            error_msg = f"File not found: {file_path}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        try:
            url = f"{self._api_url}/api/v1/files/upload"
            
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {self._token}',
            }
            
            with open(file_path, 'rb') as f:
                files = {
                    'file': (os.path.basename(file_path), f),
                }
                
                data = {}
                if description:
                    data['description'] = description
                if uploader:
                    data['uploader'] = uploader
                
                logger.info(f"Uploading file: {file_path}")
                
                response = requests.post(url, headers=headers, files=files, data=data, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"File uploaded successfully: {result.get('filename')}, file_id: {result.get('file_id')}")
                return {"success": True, "data": result}
            else:
                error_msg = f"File upload failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg, "status_code": response.status_code}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during file upload: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error during file upload: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        finally:
            # Ensure file is closed
            if 'files' in locals():
                files['file'][1].close()

    def send_file_message(self, who, file_path, wxname="", exact=False, description="", uploader=""):
        """
        Send file message via WXAuto API
        
        Args:
            who (str): Recipient name (e.g., "文件传输助手")
            file_path (str): Path to the file to send
            wxname (str): WeChat name (optional)
            exact (bool): Whether to match recipient exactly
            description (str): File description for upload (optional)
            uploader (str): Uploader name for upload (optional)
            
        Returns:
            dict: API response
        """
        if not self._api_url or not self._token:
            error_msg = "WXAuto API URL or Token not configured"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Step 1: Upload file
        upload_result = self.upload_file(file_path, description, uploader)
        if not upload_result.get("success"):
            return upload_result
        
        file_id = upload_result["data"].get("file_id")
        if not file_id:
            error_msg = "No file_id returned from upload"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        
        # Step 2: Send file using file_id
        try:
            url = f"{self._api_url}/v1/wechat/sendfile"
            
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {self._token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "wxname": wxname,
                "who": who,
                "exact": exact,
                "file_id": file_id
            }
            
            logger.info(f"Sending file to '{who}': {os.path.basename(file_path)}")
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("success"):
                    logger.info(f"File sent successfully to '{who}': {os.path.basename(file_path)}")
                    self.delete_file(file_id)
                    return {"success": True, "data": result, "file_info": upload_result["data"]}
                else:
                    error_msg = result.get("message", "Unknown error in send file")
                    logger.error(f"Send file failed: {error_msg}")
                    self.delete_file(file_id)
                    return {"success": False, "error": error_msg, "raw_data": result}
            else:
                error_msg = f"Send file API request failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                self.delete_file(file_id)
                return {"success": False, "error": error_msg, "status_code": response.status_code}
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during file send: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error during file send: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def delete_file(self, file_id):
        """
        Delete uploaded file
        
        Args:
            file_id (str): File ID to delete
            
        Returns:
            dict: Delete operation result
        """
        try:
            url = f"{self._api_url}/api/v1/files/{file_id}"
            
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {self._token}'
            }
            
            response = requests.delete(url, headers=headers, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get("message") == "文件删除成功":
                    logger.info(f"File deleted successfully: {file_id}")
                    return {"success": True}
                else:
                    error_msg = result.get("message", "Unknown deletion error")
                    logger.error(f"File deletion failed: {error_msg}")
                    return {"success": False, "error": error_msg}
            else:
                error_msg = f"Delete file API request failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during file deletion: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error during file deletion: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def download_file(self, file_id, file_path):
        """
        Download file by file_id
        
        Args:
            file_id (str): File ID to download
            file_path (str): Local path to save the downloaded file
            
        Returns:
            dict: Download operation result
        """
        try:
            url = f"{self._api_url}/api/v1/files/{file_id}/download"
            
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {self._token}'
            }
            
            response = requests.get(url, headers=headers, timeout=30, stream=True)
            
            if response.status_code == 200:
                # 确保目录存在
                os.makedirs(os.path.dirname(file_path), exist_ok=True)
                
                # 流式下载文件
                with open(file_path, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)
                
                # 验证文件是否下载成功
                if os.path.exists(file_path) and os.path.getsize(file_path) > 0:
                    logger.info(f"File downloaded successfully: {file_id} -> {file_path}")
                    return {
                        "success": True, 
                        "file_path": file_path,
                        "file_size": os.path.getsize(file_path)
                    }
                else:
                    error_msg = "Downloaded file is empty or not created"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                    
            elif response.status_code == 404:
                error_msg = f"File not found: {file_id}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            else:
                error_msg = f"Download file API request failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during file download: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except IOError as e:
            error_msg = f"File write error: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error during file download: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

    def is_online(self, wxname="") -> Dict[str, Any]:
        """
        Check if WeChat is online (wxautox specific)
        
        Args:
            wxname (str): WeChat account name
            
        Returns:
            dict: Online status result
        """
        try:
            url = f"{self._api_url}/v1/wechat/isonline"
            
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {self._token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "wxname": wxname
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"WeChat online status checked successfully: {result}")
                if not result.get("success"):
                    return {
                        "success": False,
                        "data": result
                    }
                else:
                    return {
                        "success": True,
                        "data": result
                    }
            else:
                error_msg = f"IsOnline API request failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during is_online check: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error during is_online check: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
    
    def login(self, wxname = "") -> Dict[str, Any]:
        """
        Login to WeChat
        
        Args:
            wxname (str): WeChat account name
            
        Returns:
            dict: Login operation result
        """
        try:
            url = f"{self._api_url}/v1/wechat/login"
            
            headers = {
                'accept': 'application/json',
                'Authorization': f'Bearer {self._token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "wxname": wxname
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                result = response.json()
                logger.info(f"WeChat login initiated successfully: {wxname}")
                return {
                    "success": True,
                    "data": result
                }
            else:
                error_msg = f"Login API request failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during login: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error during login: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
   
    def get_qrcode(self, wxname="") -> Dict[str, Any]:
        """
        Get WeChat login QR code and convert to base64
        
        Args:
            wxname (str): WeChat account name
            
        Returns:
            dict: QR code operation result with base64 image data
        """
        try:
            url = f"{self._api_url}/v1/wechat/qrcode"
            
            headers = {
                'accept': 'image/png',  # 期望接收图片
                'Authorization': f'Bearer {self._token}',
                'Content-Type': 'application/json'
            }
            
            payload = {
                "wxname": wxname
            }
            
            response = requests.post(url, headers=headers, json=payload, timeout=30)
            
            if response.status_code == 200:
                # 直接获取图片二进制数据
                image_data = response.content
                
                # 检查是否是有效的图片数据
                if len(image_data) == 0:
                    error_msg = "QR code image data is empty"
                    logger.error(error_msg)
                    return {"success": False, "error": error_msg}
                
                # 将图片转换为base64
                base64_image = base64.b64encode(image_data).decode('utf-8')
                data_url = f"data:image/png;base64,{base64_image}"
                
                logger.info(f"QR code retrieved successfully: {wxname}, size: {len(image_data)} bytes")
                
                return {
                    "success": True,
                    "data": {
                        "qrcode_base64": data_url,
                        "image_size": len(image_data),
                        "wxname": wxname
                    }
                }
            elif response.status_code == 404:
                error_msg = "QR code not available"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
            else:
                error_msg = f"QRCode API request failed: {response.status_code} - {response.text}"
                logger.error(error_msg)
                return {"success": False, "error": error_msg}
                
        except requests.exceptions.RequestException as e:
            error_msg = f"Network error during QR code retrieval: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}
        except Exception as e:
            error_msg = f"Unexpected error during QR code retrieval: {str(e)}"
            logger.error(error_msg)
            return {"success": False, "error": error_msg}

# Test function
if __name__ == "__main__":
    logger.info("Testing WXAuto class...")
    
    wxauto = WXAuto()

    if not wxauto.is_valid():
        logger.error("Invalid configuration. Please check your .env file.")
        sys.exit(0)

    status = wxauto.is_online()
    if not status.get("success"):
        logger.error("Wechat is not online. Please login first.")
        sys.exit(0)
    
    # Test sending to specific contact
    logger.info("\nTesting send to specific contact...")
    result = wxauto.send_text_message(
        who="文件传输助手",
        msg="这是一条给特定联系人的测试消息",
        exact=True
    )
    logger.info(f"Success: {result['success']}")
    if not result['success']:
        logger.info(f"Error: {result.get('error', 'Unknown error')}")
