import { RepoInfo } from '@/types/repoinfo';

/**
 * Generates a web URL for a file in a repository based on the repository type.
 * Supports Azure DevOps and GitHub.
 * 
 * @param repoInfo The repository information containing the URL and type.
 * @param filePath The path to the file.
 * @param lineStart The starting line number (optional).
 * @param lineEnd The ending line number (optional).
 * @returns The generated URL or an empty string if the repository type is not supported or URL is missing.
 */
export const generateFileUrl = (
  repoInfo: RepoInfo,
  filePath: string,
  lineStart?: number,
  lineEnd?: number,
  branch: string = 'main'
): string => {
  const { type, repoUrl } = repoInfo;
  
  if (!repoUrl) return '';

  const baseUrl = repoUrl.replace(/\/$/, '');

  // Normalize file path (remove leading slash if present for GitHub, keep for Azure logic below)
  const cleanPath = filePath.startsWith('/') ? filePath.substring(1) : filePath;
  
  // Azure DevOps logic
  if (type === 'azure' || baseUrl.includes('dev.azure.com') || baseUrl.includes('visualstudio.com')) {
    // Ensure path starts with / for Azure
    const azurePath = filePath.startsWith('/') ? filePath : '/' + filePath;
    const encodedPath = encodeURIComponent(azurePath);
    
    let url = `${baseUrl}?path=${encodedPath}&version=GB${branch}`; 
    
    if (lineStart) {
      url += `&line=${lineStart}&lineStartColumn=1`;
      if (lineEnd) {
        url += `&lineEnd=${lineEnd}&lineEndColumn=1`;
      } else {
        // If only start line is provided, Azure usually highlights just that line
        url += `&lineEnd=${lineStart}&lineEndColumn=1`;
      }
    }
    return url;
  } 
  
  // GitHub logic
  else if (type === 'github' || baseUrl.includes('github.com')) {
    // Format: .../blob/<branch>/path#L12-L23
    let url = `${baseUrl}/blob/${branch}/${cleanPath}`;
    if (lineStart) {
      url += `#L${lineStart}`;
      if (lineEnd) {
        url += `-L${lineEnd}`;
      }
    }
    return url;
  }
  
  // GitLab logic (generic fallback)
  else if (type === 'gitlab' || baseUrl.includes('gitlab.com')) {
    // Format: .../-/blob/<branch>/path#L12-23
    let url = `${baseUrl}/-/blob/${branch}/${cleanPath}`;
     if (lineStart) {
       url += `#L${lineStart}`;
       if (lineEnd) {
         url += `-${lineEnd}`;
       }
     }
     return url;
  }

  // Default fallback: just append path
  return `${baseUrl}/${cleanPath}`;
};
