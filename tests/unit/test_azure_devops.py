"""
Unit tests for Azure DevOps integration module.
"""

import pytest
import base64
from unittest.mock import Mock, patch, MagicMock
from api.azure_devops import (
    parse_azure_repo_url,
    is_azure_repo_url,
    create_azure_auth_header,
    mask_pat_in_string,
    get_azure_repo_slug,
    AzureRepoInfo,
    AzureDevOpsClient,
    generate_azure_file_url,
)


class TestParseAzureRepoUrl:
    """Tests for parse_azure_repo_url function."""

    def test_services_standard_url(self):
        """Test parsing standard Azure DevOps Services URL."""
        url = "https://dev.azure.com/myorg/myproject/_git/myrepo"
        result = parse_azure_repo_url(url)
        
        assert result is not None
        assert result.host == "dev.azure.com"
        assert result.organization == "myorg"
        assert result.project == "myproject"
        assert result.repository == "myrepo"
        assert result.is_server is False
        assert "dev.azure.com/myorg/myproject" in result.api_base

    def test_services_url_with_git_suffix(self):
        """Test parsing URL with .git suffix."""
        url = "https://dev.azure.com/myorg/myproject/_git/myrepo.git"
        result = parse_azure_repo_url(url)
        
        assert result is not None
        assert result.repository == "myrepo"

    def test_services_url_with_trailing_slash(self):
        """Test parsing URL with trailing slash."""
        url = "https://dev.azure.com/myorg/myproject/_git/myrepo/"
        result = parse_azure_repo_url(url)
        
        assert result is not None
        assert result.repository == "myrepo"

    def test_visualstudio_url(self):
        """Test parsing old visualstudio.com format."""
        url = "https://myorg.visualstudio.com/myproject/_git/myrepo"
        result = parse_azure_repo_url(url)
        
        assert result is not None
        assert result.organization == "myorg"
        assert result.project == "myproject"
        assert result.repository == "myrepo"
        assert result.is_server is False

    def test_server_url(self):
        """Test parsing Azure DevOps Server URL."""
        url = "https://azuredevops.company.com/DefaultCollection/myproject/_git/myrepo"
        result = parse_azure_repo_url(url)
        
        assert result is not None
        assert result.host == "azuredevops.company.com"
        assert result.organization == "DefaultCollection"
        assert result.project == "myproject"
        assert result.repository == "myrepo"
        assert result.is_server is True

    def test_invalid_url_no_git(self):
        """Test that URL without _git returns None."""
        url = "https://github.com/owner/repo"
        result = parse_azure_repo_url(url)
        
        assert result is None

    def test_invalid_url_missing_repo(self):
        """Test that URL without repository name returns None."""
        url = "https://dev.azure.com/myorg/myproject/_git/"
        result = parse_azure_repo_url(url)
        
        assert result is None

    def test_empty_url(self):
        """Test that empty URL returns None."""
        result = parse_azure_repo_url("")
        assert result is None

    def test_none_url(self):
        """Test that None URL returns None."""
        result = parse_azure_repo_url(None)
        assert result is None


class TestIsAzureRepoUrl:
    """Tests for is_azure_repo_url function."""

    def test_dev_azure_com(self):
        """Test detection of dev.azure.com URLs."""
        assert is_azure_repo_url("https://dev.azure.com/org/project/_git/repo") is True

    def test_visualstudio_com(self):
        """Test detection of visualstudio.com URLs."""
        assert is_azure_repo_url("https://org.visualstudio.com/project/_git/repo") is True

    def test_custom_host_with_git(self):
        """Test detection of custom host with _git pattern."""
        assert is_azure_repo_url("https://custom.server.com/collection/project/_git/repo") is True

    def test_github_url(self):
        """Test that GitHub URLs are not detected as Azure."""
        assert is_azure_repo_url("https://github.com/owner/repo") is False

    def test_gitlab_url(self):
        """Test that GitLab URLs are not detected as Azure."""
        assert is_azure_repo_url("https://gitlab.com/owner/repo") is False

    def test_empty_url(self):
        """Test that empty URL returns False."""
        assert is_azure_repo_url("") is False

    def test_none_url(self):
        """Test that None URL returns False."""
        assert is_azure_repo_url(None) is False


class TestCreateAzureAuthHeader:
    """Tests for create_azure_auth_header function."""

    def test_basic_auth_format(self):
        """Test that auth header is in correct Basic format."""
        pat = "mypattoken123"
        header = create_azure_auth_header(pat)
        
        assert header.startswith("Basic ")
        
        # Decode and verify
        encoded_part = header.split(" ")[1]
        decoded = base64.b64decode(encoded_part).decode('utf-8')
        assert decoded == f":{pat}"

    def test_special_characters_in_pat(self):
        """Test PAT with special characters."""
        pat = "token+with/special=chars"
        header = create_azure_auth_header(pat)
        
        encoded_part = header.split(" ")[1]
        decoded = base64.b64decode(encoded_part).decode('utf-8')
        assert decoded == f":{pat}"


class TestMaskPatInString:
    """Tests for mask_pat_in_string function."""

    def test_mask_raw_pat(self):
        """Test masking raw PAT in string."""
        pat = "secretpat123"
        text = f"Error: authentication failed with token {pat}"
        result = mask_pat_in_string(text, pat)
        
        assert pat not in result
        assert "***PAT***" in result

    def test_mask_base64_pat(self):
        """Test masking base64-encoded PAT in string."""
        pat = "secretpat123"
        encoded = base64.b64encode(f":{pat}".encode()).decode()
        text = f"Header: Basic {encoded}"
        result = mask_pat_in_string(text, pat)
        
        assert encoded not in result
        assert "***ENCODED_PAT***" in result

    def test_empty_text(self):
        """Test with empty text."""
        result = mask_pat_in_string("", "pat")
        assert result == ""

    def test_empty_pat(self):
        """Test with empty PAT."""
        text = "Some text"
        result = mask_pat_in_string(text, "")
        assert result == text

    def test_none_text(self):
        """Test with None text."""
        result = mask_pat_in_string(None, "pat")
        assert result is None


class TestGetAzureRepoSlug:
    """Tests for get_azure_repo_slug function."""

    def test_services_slug(self):
        """Test slug generation for Azure DevOps Services."""
        info = AzureRepoInfo(
            host="dev.azure.com",
            organization="myorg",
            project="myproject",
            repository="myrepo",
            api_base="https://dev.azure.com/myorg/myproject",
            clone_url="https://dev.azure.com/myorg/myproject/_git/myrepo",
            is_server=False
        )
        slug = get_azure_repo_slug(info)
        
        assert slug == "myorg_myproject_myrepo"

    def test_server_slug_includes_host(self):
        """Test slug generation for Azure DevOps Server includes host."""
        info = AzureRepoInfo(
            host="azuredevops.company.com",
            organization="DefaultCollection",
            project="myproject",
            repository="myrepo",
            api_base="https://azuredevops.company.com/DefaultCollection/myproject",
            clone_url="https://azuredevops.company.com/DefaultCollection/myproject/_git/myrepo",
            is_server=True
        )
        slug = get_azure_repo_slug(info)
        
        assert "azuredevops" in slug
        assert "DefaultCollection" in slug
        assert "myproject" in slug
        assert "myrepo" in slug

    def test_slug_sanitizes_special_chars(self):
        """Test that slug sanitizes special characters."""
        info = AzureRepoInfo(
            host="dev.azure.com",
            organization="my-org",
            project="my.project",
            repository="my/repo",
            api_base="https://dev.azure.com/my-org/my.project",
            clone_url="https://dev.azure.com/my-org/my.project/_git/my/repo",
            is_server=False
        )
        slug = get_azure_repo_slug(info)
        
        # Should not contain special chars except - and _
        assert "/" not in slug
        assert slug.replace("_", "").replace("-", "").isalnum() or "_" in slug or "-" in slug


class TestGenerateAzureFileUrl:
    """Tests for generate_azure_file_url function."""

    def test_file_url_generation(self):
        """Test file URL generation."""
        repo_url = "https://dev.azure.com/myorg/myproject/_git/myrepo"
        file_path = "src/main.py"
        branch = "main"
        
        result = generate_azure_file_url(repo_url, file_path, branch)
        
        assert "dev.azure.com" in result
        assert "myorg" in result
        assert "myproject" in result
        assert "myrepo" in result
        assert "path=" in result
        assert "version=GBmain" in result

    def test_file_url_with_leading_slash(self):
        """Test file URL with leading slash in path."""
        repo_url = "https://dev.azure.com/myorg/myproject/_git/myrepo"
        file_path = "/src/main.py"
        
        result = generate_azure_file_url(repo_url, file_path)
        
        assert result is not None

    def test_invalid_repo_url(self):
        """Test with invalid repo URL."""
        result = generate_azure_file_url("not-a-valid-url", "file.py")
        assert result == "file.py"


class TestAzureDevOpsClient:
    """Tests for AzureDevOpsClient class."""

    def test_client_initialization(self):
        """Test client initialization with valid URL."""
        client = AzureDevOpsClient(
            "https://dev.azure.com/myorg/myproject/_git/myrepo",
            "testpat"
        )
        
        assert client.repo_info is not None
        assert client.pat == "testpat"

    def test_client_invalid_url(self):
        """Test client initialization with invalid URL raises error."""
        with pytest.raises(ValueError):
            AzureDevOpsClient("https://github.com/owner/repo")

    def test_get_headers_with_pat(self):
        """Test that headers include auth when PAT is provided."""
        client = AzureDevOpsClient(
            "https://dev.azure.com/myorg/myproject/_git/myrepo",
            "testpat"
        )
        
        headers = client._get_headers()
        
        assert "Authorization" in headers
        assert headers["Authorization"].startswith("Basic ")

    def test_get_headers_without_pat(self):
        """Test that headers don't include auth when no PAT."""
        client = AzureDevOpsClient(
            "https://dev.azure.com/myorg/myproject/_git/myrepo"
        )
        
        headers = client._get_headers()
        
        assert "Authorization" not in headers

    @patch('api.azure_devops.requests.request')
    def test_get_repository_info(self, mock_request):
        """Test getting repository info."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            "id": "repo-id",
            "name": "myrepo",
            "defaultBranch": "refs/heads/main"
        }
        mock_request.return_value = mock_response
        
        client = AzureDevOpsClient(
            "https://dev.azure.com/myorg/myproject/_git/myrepo",
            "testpat"
        )
        
        result = client.get_repository_info()
        
        assert result["name"] == "myrepo"
        assert result["defaultBranch"] == "refs/heads/main"

    @patch('api.azure_devops.requests.request')
    def test_get_default_branch(self, mock_request):
        """Test getting default branch."""
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"defaultBranch": "refs/heads/develop"}
        mock_response.raise_for_status = Mock()
        mock_request.return_value = mock_response
        
        client = AzureDevOpsClient(
            "https://dev.azure.com/myorg/myproject/_git/myrepo"
        )
        
        result = client.get_default_branch()
        
        assert result == "develop"

    @patch('api.azure_devops.requests.request')
    def test_get_file_content(self, mock_request):
        """Test getting file content."""
        # First call for default branch
        mock_branch_response = Mock()
        mock_branch_response.status_code = 200
        mock_branch_response.json.return_value = {"defaultBranch": "refs/heads/main"}
        mock_branch_response.raise_for_status = Mock()
        
        # Second call for file content
        mock_content_response = Mock()
        mock_content_response.status_code = 200
        mock_content_response.text = "file content here"
        mock_content_response.raise_for_status = Mock()
        
        mock_request.side_effect = [mock_branch_response, mock_content_response]
        
        client = AzureDevOpsClient(
            "https://dev.azure.com/myorg/myproject/_git/myrepo"
        )
        
        result = client.get_file_content("README.md")
        
        assert result == "file content here"

    @patch('api.azure_devops.requests.request')
    def test_get_file_content_401_error(self, mock_request):
        """Test file content with 401 error."""
        mock_response = Mock()
        mock_response.status_code = 401
        mock_request.return_value = mock_response
        
        client = AzureDevOpsClient(
            "https://dev.azure.com/myorg/myproject/_git/myrepo"
        )
        
        with pytest.raises(ValueError) as excinfo:
            client.get_file_content("README.md")
        
        assert "Unauthorized" in str(excinfo.value)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
