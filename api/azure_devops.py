"""
Azure DevOps integration module for DeepWiki.
Handles URL parsing, API calls, and git operations for Azure DevOps Services and Server.
"""

import re
import base64
import logging
import requests
from urllib.parse import urlparse, quote
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass

logger = logging.getLogger(__name__)

# Default API version for Azure DevOps REST API
DEFAULT_API_VERSION = "7.1"


@dataclass
class AzureRepoInfo:
    """Data class to hold parsed Azure DevOps repository information."""
    host: str
    organization: str  # org for Services, collection for Server
    project: str
    repository: str
    api_base: str
    clone_url: str
    is_server: bool  # True for Azure DevOps Server/TFS, False for Services


def parse_azure_repo_url(repo_url: str) -> Optional[AzureRepoInfo]:
    """
    Parse an Azure DevOps repository URL and extract components.
    
    Supports:
    - Azure DevOps Services: https://dev.azure.com/{org}/{project}/_git/{repo}
    - Azure DevOps Services (old): https://{org}.visualstudio.com/{project}/_git/{repo}
    - Azure DevOps Server/TFS: https://{host}/{collection}/{project}/_git/{repo}
    
    Args:
        repo_url: The Azure DevOps repository URL
        
    Returns:
        AzureRepoInfo with parsed components, or None if not a valid Azure URL
    """
    if not repo_url:
        return None
    
    repo_url = repo_url.strip().rstrip('/')
    
    # Remove .git suffix if present
    if repo_url.endswith('.git'):
        repo_url = repo_url[:-4]
    
    try:
        parsed = urlparse(repo_url)
        host = parsed.netloc.lower()
        path_parts = [p for p in parsed.path.split('/') if p]
        
        logger.debug(f"Parsing Azure URL: host={host}, path_parts={path_parts}")
        
        # Check if this is an Azure DevOps URL
        is_azure = False
        is_server = False
        
        # Azure DevOps Services patterns
        if 'dev.azure.com' in host:
            is_azure = True
            is_server = False
        elif 'visualstudio.com' in host:
            is_azure = True
            is_server = False
        # Check for _git in path (indicates Azure DevOps)
        elif '_git' in path_parts:
            is_azure = True
            is_server = True  # Assume Server/TFS for custom hosts
        
        if not is_azure:
            logger.warning(f"Not an Azure DevOps URL: {repo_url}")
            return None
        
        # Find the _git position in path
        try:
            git_index = path_parts.index('_git')
        except ValueError:
            logger.warning(f"Could not find '_git' in Azure DevOps URL: {repo_url}")
            return None
        
        # Extract repository name (after _git)
        if git_index + 1 >= len(path_parts):
            logger.warning(f"Missing repository name in Azure DevOps URL: {repo_url}")
            return None
        repository = path_parts[git_index + 1]
        
        # Extract project (before _git)
        if git_index < 1:
            logger.warning(f"Missing project in Azure DevOps URL: {repo_url}")
            return None
        project = path_parts[git_index - 1]
        
        # Extract organization/collection
        if host == 'dev.azure.com':
            # Services format: https://dev.azure.com/{org}/{project}/_git/{repo}
            if git_index < 2:
                logger.warning(f"Missing organization in Azure DevOps URL: {repo_url}")
                return None
            organization = path_parts[0]
        elif 'visualstudio.com' in host:
            # Old Services format: https://{org}.visualstudio.com/{project}/_git/{repo}
            organization = host.split('.')[0]
        else:
            # Server/TFS format: https://{host}/{collection}/{project}/_git/{repo}
            if git_index < 2:
                logger.warning(f"Missing collection in Azure DevOps URL: {repo_url}")
                return None
            organization = path_parts[0]
        
        # Build API base URL
        scheme = parsed.scheme or 'https'
        if host == 'dev.azure.com':
            api_base = f"{scheme}://{host}/{organization}/{project}"
        elif 'visualstudio.com' in host:
            api_base = f"{scheme}://{host}/{project}"
        else:
            # Server/TFS: Keep the full path including collection
            # For: https://host/collection/project/_git/repo
            # API should be: https://host/collection/project
            api_base = f"{scheme}://{host}/{organization}/{project}"
        
        # Clone URL is the same as repo URL (without .git)
        clone_url = repo_url
        
        logger.debug(f"Parsed Azure DevOps: org={organization}, project={project}, repo={repository}, api_base={api_base}")
        
        return AzureRepoInfo(
            host=host,
            organization=organization,
            project=project,
            repository=repository,
            api_base=api_base,
            clone_url=clone_url,
            is_server=is_server
        )
        
    except Exception as e:
        logger.error(f"Error parsing Azure DevOps URL '{repo_url}': {e}")
        return None


def is_azure_repo_url(repo_url: str) -> bool:
    """
    Check if a URL is an Azure DevOps repository URL.
    
    Args:
        repo_url: The URL to check
        
    Returns:
        True if the URL is an Azure DevOps repository URL
    """
    if not repo_url:
        return False
    
    repo_url = repo_url.lower()
    
    # Check for common Azure DevOps domains
    if 'dev.azure.com' in repo_url:
        return True
    if 'visualstudio.com' in repo_url:
        return True
    
    # Check for _git in path (Azure DevOps pattern)
    if '/_git/' in repo_url:
        return True
    
    return False


def create_azure_auth_header(pat: str) -> str:
    """
    Create the Basic Authentication header value for Azure DevOps.
    
    Azure DevOps uses Basic Auth with an empty username and PAT as password.
    
    Args:
        pat: Personal Access Token
        
    Returns:
        The Authorization header value (e.g., "Basic base64encoded")
    """
    # Azure DevOps Basic Auth: ":{PAT}" encoded in base64
    auth_string = f":{pat}"
    encoded = base64.b64encode(auth_string.encode('utf-8')).decode('utf-8')
    return f"Basic {encoded}"


def mask_pat_in_string(text: str, pat: str) -> str:
    """
    Mask PAT in a string to prevent exposure in logs or error messages.
    
    Args:
        text: The text that may contain the PAT
        pat: The PAT to mask
        
    Returns:
        Text with PAT masked
    """
    if not pat or not text:
        return text
    
    # Mask raw PAT
    masked = text.replace(pat, "***PAT***")
    
    # Also mask base64-encoded PAT (both with and without empty username)
    try:
        encoded_with_colon = base64.b64encode(f":{pat}".encode('utf-8')).decode('utf-8')
        masked = masked.replace(encoded_with_colon, "***ENCODED_PAT***")
        
        encoded_plain = base64.b64encode(pat.encode('utf-8')).decode('utf-8')
        masked = masked.replace(encoded_plain, "***ENCODED_PAT***")
    except Exception:
        pass
    
    return masked


def get_azure_repo_slug(info: AzureRepoInfo) -> str:
    """
    Generate a unique slug for cache/database naming.
    
    Args:
        info: Parsed Azure repository info
        
    Returns:
        A slug in format: host_org_project_repo (sanitized)
    """
    # Sanitize each component
    def sanitize(s: str) -> str:
        # Replace dots, slashes, and other special chars with underscores
        return re.sub(r'[^a-zA-Z0-9_-]', '_', s)
    
    # For dev.azure.com, we can simplify the slug
    if info.host == 'dev.azure.com':
        return f"{sanitize(info.organization)}_{sanitize(info.project)}_{sanitize(info.repository)}"
    else:
        # For custom hosts, include host to ensure uniqueness
        host_part = sanitize(info.host.split('.')[0])  # Use first part of host
        return f"{host_part}_{sanitize(info.organization)}_{sanitize(info.project)}_{sanitize(info.repository)}"


class AzureDevOpsClient:
    """Client for interacting with Azure DevOps REST API."""
    
    def __init__(self, repo_url: str, pat: Optional[str] = None, api_version: str = DEFAULT_API_VERSION):
        """
        Initialize Azure DevOps client.
        
        Args:
            repo_url: Azure DevOps repository URL
            pat: Personal Access Token (optional for public repos)
            api_version: API version to use
        """
        self.repo_info = parse_azure_repo_url(repo_url)
        if not self.repo_info:
            raise ValueError(f"Invalid Azure DevOps URL: {repo_url}. Expected format: https://{{host}}/{{collection}}/{{project}}/_git/{{repo}}")
        
        self.pat = pat
        self.api_version = api_version
        
        logger.debug(f"Azure DevOps Client initialized:")
        logger.debug(f"  Host: {self.repo_info.host}")
        logger.debug(f"  Organization/Collection: {self.repo_info.organization}")
        logger.debug(f"  Project: {self.repo_info.project}")
        logger.debug(f"  Repository: {self.repo_info.repository}")
        logger.debug(f"  API Base: {self.repo_info.api_base}")
        logger.debug(f"  Is Server: {self.repo_info.is_server}")
        logger.debug(f"  Has PAT: {bool(self.pat)}")
        
    def _get_headers(self) -> Dict[str, str]:
        """Get HTTP headers for API requests."""
        headers = {
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }
        if self.pat:
            headers['Authorization'] = create_azure_auth_header(self.pat)
        return headers
    
    def _make_request(self, url: str, method: str = 'GET', **kwargs) -> requests.Response:
        """
        Make an HTTP request with proper error handling and PAT masking.
        
        Args:
            url: Request URL
            method: HTTP method
            **kwargs: Additional arguments for requests
            
        Returns:
            Response object
        """
        headers = kwargs.pop('headers', {})
        headers.update(self._get_headers())
        
        try:
            response = requests.request(method, url, headers=headers, **kwargs)
            return response
        except requests.RequestException as e:
            # Mask PAT in error message
            error_msg = str(e)
            if self.pat:
                error_msg = mask_pat_in_string(error_msg, self.pat)
            raise requests.RequestException(error_msg)
    
    def get_repository_info(self) -> Dict[str, Any]:
        """
        Get repository metadata including default branch.
        
        Returns:
            Repository information dict
        """
        url = f"{self.repo_info.api_base}/_apis/git/repositories/{self.repo_info.repository}"
        params = {'api-version': self.api_version}
        
        logger.debug(f"Getting repo info from: {url}")
        logger.debug(f"API base: {self.repo_info.api_base}")
        logger.debug(f"Repository: {self.repo_info.repository}")
        
        try:
            response = self._make_request(url, params=params)
            logger.debug(f"Response status: {response.status_code}")
            logger.debug(f"Response headers: {response.headers}")
            logger.debug(f"Response body (first 500 chars): {response.text[:500]}")
        except Exception as e:
            logger.error(f"Error making request to {url}: {e}")
            raise

        if response.status_code == 401:
            raise ValueError("Unauthorized: Invalid or missing PAT. Please check your Personal Access Token.")
        elif response.status_code == 403:
            raise ValueError("Forbidden: Your PAT doesn't have permission to access this repository. Ensure it has 'Code (Read)' scope.")
        elif response.status_code == 404:
            detail = response.text
            raise ValueError(f"Repository not found: {self.repo_info.repository}. API URL: {url}. Response: {detail[:200]}")
        
        response.raise_for_status()
        return response.json()
    
    def get_default_branch(self) -> str:
        """
        Get the default branch of the repository.
        
        Returns:
            Default branch name (e.g., 'main', 'master')
        """
        try:
            repo_info = self.get_repository_info()
            default_branch = repo_info.get('defaultBranch', 'refs/heads/main')
            # Remove refs/heads/ prefix if present
            if default_branch.startswith('refs/heads/'):
                default_branch = default_branch[len('refs/heads/'):]
            return default_branch
        except Exception as e:
            logger.warning(f"Could not get default branch, using 'main': {e}")
            return 'main'
    
    def get_file_tree(self, branch: Optional[str] = None) -> list:
        """
        Get the complete file tree of the repository.
        
        Args:
            branch: Branch name (uses default branch if not specified)
            
        Returns:
            List of file paths
        """
        if not branch:
            branch = self.get_default_branch()
        
        url = f"{self.repo_info.api_base}/_apis/git/repositories/{self.repo_info.repository}/items"
        params = {
            'scopePath': '/',
            'recursionLevel': 'Full',
            'includeContentMetadata': 'true',
            'versionDescriptor.version': branch,
            'api-version': self.api_version
        }
        
        response = self._make_request(url, params=params)
        
        if response.status_code == 401:
            raise ValueError("Unauthorized: Invalid or missing PAT.")
        elif response.status_code == 403:
            raise ValueError("Forbidden: Insufficient permissions.")
        elif response.status_code == 404:
            raise ValueError(f"Repository or branch not found: {branch}")
        
        response.raise_for_status()
        data = response.json()
        
        # Extract file paths from the response
        files = []
        items = data.get('value', [])
        for item in items:
            if item.get('gitObjectType') == 'blob':
                path = item.get('path', '')
                if path.startswith('/'):
                    path = path[1:]  # Remove leading slash
                files.append(path)
        
        return files
    
    def get_file_content(self, file_path: str, branch: Optional[str] = None) -> str:
        """
        Get the content of a specific file.
        
        Args:
            file_path: Path to the file
            branch: Branch name (uses default branch if not specified)
            
        Returns:
            File content as string
        """
        if not branch:
            branch = self.get_default_branch()
        
        # Ensure path starts with /
        if not file_path.startswith('/'):
            file_path = '/' + file_path
        
        url = f"{self.repo_info.api_base}/_apis/git/repositories/{self.repo_info.repository}/items"
        params = {
            'path': file_path,
            'includeContent': 'true',
            'versionDescriptor.version': branch,
            'api-version': self.api_version,
            '$format': 'text'  # Get raw text content
        }
        
        response = self._make_request(url, params=params)
        
        if response.status_code == 401:
            raise ValueError("Unauthorized: Invalid or missing PAT.")
        elif response.status_code == 403:
            raise ValueError("Forbidden: Insufficient permissions.")
        elif response.status_code == 404:
            raise ValueError(f"File not found: {file_path}")
        
        response.raise_for_status()
        return response.text
    
    def get_readme(self, branch: Optional[str] = None) -> str:
        """
        Try to get the README file content.
        
        Args:
            branch: Branch name (uses default branch if not specified)
            
        Returns:
            README content or empty string if not found
        """
        readme_names = ['README.md', 'README.MD', 'readme.md', 'README.txt', 'README']
        
        for readme_name in readme_names:
            try:
                return self.get_file_content(readme_name, branch)
            except ValueError as e:
                if 'not found' in str(e).lower():
                    continue
                raise
            except Exception:
                continue
        
        logger.info("No README file found in repository")
        return ''
    
    def get_repo_structure(self, branch: Optional[str] = None) -> Dict[str, Any]:
        """
        Get repository structure including file tree and README.
        
        Args:
            branch: Branch name (uses default branch if not specified)
            
        Returns:
            Dict with 'file_tree', 'readme', and 'default_branch' keys
        """
        if not branch:
            branch = self.get_default_branch()
        
        file_tree = self.get_file_tree(branch)
        readme = self.get_readme(branch)
        
        return {
            'file_tree': '\n'.join(file_tree),
            'readme': readme,
            'default_branch': branch
        }


def generate_azure_file_url(repo_url: str, file_path: str, branch: str = 'main') -> str:
    """
    Generate a web URL for viewing a file in Azure DevOps.
    
    Args:
        repo_url: Repository URL
        file_path: Path to the file
        branch: Branch name
        
    Returns:
        Web URL for the file
    """
    info = parse_azure_repo_url(repo_url)
    if not info:
        return file_path
    
    # Ensure file_path starts with /
    if not file_path.startswith('/'):
        file_path = '/' + file_path
    
    # URL encode the path
    encoded_path = quote(file_path, safe='/')
    
    # Azure DevOps file URL format
    return f"{info.api_base}/_git/{info.repository}?path={encoded_path}&version=GB{branch}"
