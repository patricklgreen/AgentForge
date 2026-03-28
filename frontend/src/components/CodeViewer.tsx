import React, { useState } from "react";
import Editor from "@monaco-editor/react";
import { Copy, Check, FileCode } from "lucide-react";
import { clsx } from "clsx";
import type { CodeFile } from "../types";

interface CodeViewerProps {
  files:   CodeFile[];
  height?: string;
}

const LANGUAGE_MAP: Record<string, string> = {
  python:     "python",
  typescript: "typescript",
  javascript: "javascript",
  java:       "java",
  go:         "go",
  rust:       "rust",
  ruby:       "ruby",
  csharp:     "csharp",
  yaml:       "yaml",
  json:       "json",
  markdown:   "markdown",
  bash:       "shell",
  sql:        "sql",
  terraform:  "hcl",
  dockerfile: "dockerfile",
  makefile:   "makefile",
  html:       "html",
  css:        "css",
  plaintext:  "plaintext",
};

export function CodeViewer({ files, height = "400px" }: CodeViewerProps) {
  const [selectedIndex, setSelectedIndex] = useState(0);
  const [copied, setCopied] = useState(false);

  if (!files.length) {
    return (
      <div className="bg-gray-950 border border-gray-800 rounded-xl flex items-center justify-center py-12 text-gray-600">
        <div className="text-center">
          <FileCode className="h-8 w-8 mx-auto mb-2 opacity-50" />
          <p className="text-sm">No files to display</p>
        </div>
      </div>
    );
  }

  const safeIndex = Math.min(selectedIndex, files.length - 1);
  const selectedFile = files[safeIndex];

  const handleCopy = async () => {
    if (selectedFile?.content) {
      await navigator.clipboard.writeText(selectedFile.content);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  const displayedFiles = files.slice(0, 15);
  const overflow = files.length - displayedFiles.length;

  return (
    <div className="bg-gray-950 rounded-xl border border-gray-800 overflow-hidden">
      {/* File tab bar */}
      <div className="flex items-center gap-0.5 bg-gray-900 px-2 py-1.5 border-b border-gray-800 overflow-x-auto">
        {displayedFiles.map((file, idx) => {
          const filename = file.path.split("/").pop() ?? file.path;
          const isActive = idx === safeIndex;
          return (
            <button
              key={file.path}
              onClick={() => setSelectedIndex(idx)}
              title={file.path}
              className={clsx(
                "px-3 py-1.5 rounded text-xs font-mono whitespace-nowrap transition-colors max-w-[160px] truncate",
                isActive
                  ? "bg-gray-700 text-white"
                  : "text-gray-500 hover:text-gray-300 hover:bg-gray-800"
              )}
            >
              {filename}
            </button>
          );
        })}
        {overflow > 0 && (
          <span className="text-xs text-gray-600 px-2 flex-shrink-0">
            +{overflow} more
          </span>
        )}
      </div>

      {/* File path and actions */}
      <div className="flex items-center justify-between px-4 py-2 bg-gray-900 border-b border-gray-800">
        <span className="text-xs text-indigo-400 font-mono truncate max-w-[70%]">
          {selectedFile?.path}
        </span>
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-xs text-gray-500 hover:text-gray-300 transition-colors flex-shrink-0"
          title="Copy file content"
        >
          {copied ? (
            <>
              <Check className="h-3.5 w-3.5 text-green-400" />
              <span className="text-green-400">Copied</span>
            </>
          ) : (
            <>
              <Copy className="h-3.5 w-3.5" />
              Copy
            </>
          )}
        </button>
      </div>

      {/* Monaco Editor */}
      <Editor
        height={height}
        language={
          LANGUAGE_MAP[selectedFile?.language?.toLowerCase() ?? ""] ?? "plaintext"
        }
        value={selectedFile?.content ?? ""}
        theme="vs-dark"
        options={{
          readOnly:              true,
          minimap:               { enabled: false },
          scrollBeyondLastLine:  false,
          fontSize:              13,
          lineNumbers:           "on",
          wordWrap:              "on",
          automaticLayout:       true,
          padding:               { top: 12, bottom: 12 },
          renderLineHighlight:   "none",
          scrollbar: {
            vertical:             "auto",
            horizontal:           "auto",
            verticalScrollbarSize: 6,
          },
        }}
      />
    </div>
  );
}
