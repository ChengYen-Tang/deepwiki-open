import { RepoInfo } from '@/types/repoinfo';
import { generateFileUrl } from './fileUrlGenerator';

const normalizeSlashes = (p: string): string => p.replace(/\\/g, '/');

const resolveRepoRelativePath = (
  candidatePath: string,
  knownFilePaths?: string[],
  preferredFilePaths?: string[]
): string | null => {
  if (!candidatePath) return null;
  if (!knownFilePaths || knownFilePaths.length === 0) return normalizeSlashes(candidatePath);

  const normalizedCandidate = normalizeSlashes(candidatePath).replace(/^\//, '');
  const normalizedKnown = knownFilePaths.map(p => normalizeSlashes(p).replace(/^\//, '')).filter(Boolean);

  // 1) Exact match
  if (normalizedKnown.includes(normalizedCandidate)) return normalizedCandidate;

  const normalizedPreferred = (preferredFilePaths || [])
    .map(p => normalizeSlashes(p).replace(/^\//, ''))
    .filter(Boolean);

  // 2) Suffix match (handles partial paths like "src/foo.cs")
  const suffixMatches = normalizedKnown.filter(p => p.endsWith('/' + normalizedCandidate) || p === normalizedCandidate);
  if (suffixMatches.length === 1) return suffixMatches[0];
  if (suffixMatches.length > 1 && normalizedPreferred.length > 0) {
    const preferredSuffixMatches = suffixMatches.filter(p => normalizedPreferred.includes(p));
    if (preferredSuffixMatches.length === 1) return preferredSuffixMatches[0];
  }

  // 3) Basename match (handles only filename provided)
  const baseName = normalizedCandidate.split('/').pop();
  if (!baseName) return null;
  const baseMatches = normalizedKnown.filter(p => p.split('/').pop() === baseName);
  if (baseMatches.length === 1) return baseMatches[0];
  if (baseMatches.length > 1 && normalizedPreferred.length > 0) {
    const preferredBaseMatches = baseMatches.filter(p => normalizedPreferred.includes(p));
    if (preferredBaseMatches.length === 1) return preferredBaseMatches[0];
  }

  // Ambiguous or not found
  return null;
};

/**
 * Processes wiki content to replace empty links with generated file URLs.
 * 
 * @param content The raw markdown content.
 * @param repoInfo The repository information.
 * @returns The processed markdown content with valid links.
 */
export const processWikiContent = (
  content: string,
  repoInfo: RepoInfo,
  knownFilePaths?: string[],
  defaultBranch: string = 'main',
  preferredFilePaths?: string[]
): string => {
  if (!content || !repoInfo) return content;

  // Regex to match [path:lines]() or [path]()
  // Captures: 1=path, 2=startLine, 3=endLine (optional)
  // Example: [BankSinopacApi/DependencyInjection.cs:12-23]()
  const regex = /\[([^:\]\n]+)(?::(\d+)(?:-(\d+))?)?\]\(\)/g;
  
  return content.replace(regex, (match, rawPath, start, end) => {
    const resolvedPath = resolveRepoRelativePath(rawPath, knownFilePaths, preferredFilePaths);
    if (!resolvedPath) return match;

    const startLine = start ? parseInt(start, 10) : undefined;
    const endLine = end ? parseInt(end, 10) : undefined;

    const normalizedStart = startLine && startLine > 0 ? startLine : undefined;
    const normalizedEnd = endLine && endLine > 0 ? endLine : undefined;
    const finalStart = normalizedStart;
    const finalEnd =
      finalStart && normalizedEnd
        ? Math.max(finalStart, normalizedEnd)
        : normalizedEnd;

    const url = generateFileUrl(repoInfo, resolvedPath, finalStart, finalEnd, defaultBranch);
    if (!url) return match;

    const label = `${rawPath}${start ? ':' + start + (end ? '-' + end : '') : ''}`;
    return `[${label}](${url})`;
  });
};
