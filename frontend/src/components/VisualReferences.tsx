import React, { useState } from 'react';
import { Upload, X, Plus, Link, Image, Loader2, AlertCircle } from 'lucide-react';
import { useMutation } from '@tanstack/react-query';
import { projectsApi } from '../api/client';
import type { VisualReference } from '../types/index';

interface VisualReferencesProps {
  references: VisualReference[];
  onChange: (references: VisualReference[]) => void;
}

export const VisualReferences: React.FC<VisualReferencesProps> = ({
  references,
  onChange,
}) => {
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [urlInput, setUrlInput] = useState('');
  const [urlDescription, setUrlDescription] = useState('');
  const [dragOver, setDragOver] = useState(false);

  const uploadMutation = useMutation({
    mutationFn: ({ file, description }: { file: File; description?: string }) =>
      projectsApi.uploadVisualReference(file, description),
    onSuccess: (data) => {
      const newReference: VisualReference = {
        type: 'upload',
        file_name: data.file_name,
        s3_key: data.s3_key,
        description: data.description,
        preview_url: data.preview_url,
      };
      onChange([...references, newReference]);
    },
  });

  const handleFileUpload = (files: FileList | null) => {
    if (!files || files.length === 0) return;
    
    const file = files[0];
    
    // Validate file type
    if (!file.type.startsWith('image/')) {
      alert('Please select an image file');
      return;
    }
    
    // Validate file size (10MB)
    if (file.size > 10 * 1024 * 1024) {
      alert('File size must be less than 10MB');
      return;
    }

    uploadMutation.mutate({ file });
  };

  const handleUrlSubmit = () => {
    if (!urlInput.trim()) return;
    
    const newReference: VisualReference = {
      type: 'url',
      url: urlInput.trim(),
      description: urlDescription.trim() || undefined,
    };
    
    onChange([...references, newReference]);
    setUrlInput('');
    setUrlDescription('');
    setShowUrlInput(false);
  };

  const removeReference = (index: number) => {
    onChange(references.filter((_, i) => i !== index));
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    handleFileUpload(e.dataTransfer.files);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
  };

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <label className="block text-sm font-medium text-gray-300">
          Visual References (Optional)
        </label>
        <span className="text-xs text-gray-500">
          Upload mockups, designs, or screenshots
        </span>
      </div>

      {/* Upload Area */}
      <div
        className={`border-2 border-dashed rounded-xl p-6 text-center transition-colors ${
          dragOver 
            ? 'border-indigo-500 bg-indigo-500/10' 
            : 'border-gray-700 hover:border-gray-600'
        }`}
        onDrop={handleDrop}
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
      >
        <input
          type="file"
          accept="image/*"
          onChange={(e) => handleFileUpload(e.target.files)}
          className="hidden"
          id="visual-upload"
          disabled={uploadMutation.isPending}
        />
        
        <div className="space-y-3">
          <div className="flex justify-center">
            {uploadMutation.isPending ? (
              <Loader2 className="h-8 w-8 text-indigo-400 animate-spin" />
            ) : (
              <Upload className="h-8 w-8 text-gray-400" />
            )}
          </div>
          
          <div>
            <p className="text-sm text-gray-300">
              {uploadMutation.isPending ? 'Uploading...' : 'Drop images here or click to upload'}
            </p>
            <p className="text-xs text-gray-500 mt-1">
              PNG, JPG, GIF up to 10MB
            </p>
          </div>
          
          <div className="flex justify-center gap-2">
            <label
              htmlFor="visual-upload"
              className={`px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg text-sm cursor-pointer transition-colors ${
                uploadMutation.isPending ? 'opacity-50 cursor-not-allowed' : ''
              }`}
            >
              <Upload className="h-4 w-4 inline mr-2" />
              Upload File
            </label>
            
            <button
              type="button"
              onClick={() => setShowUrlInput(true)}
              disabled={uploadMutation.isPending}
              className="px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-200 rounded-lg text-sm transition-colors disabled:opacity-50"
            >
              <Link className="h-4 w-4 inline mr-2" />
              Add URL
            </button>
          </div>
        </div>
      </div>

      {/* URL Input Modal */}
      {showUrlInput && (
        <div className="bg-gray-800 border border-gray-700 rounded-xl p-4 space-y-3">
          <h4 className="text-sm font-medium text-gray-200">Add Image URL</h4>
          
          <input
            type="url"
            value={urlInput}
            onChange={(e) => setUrlInput(e.target.value)}
            placeholder="https://example.com/mockup.png"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
          />
          
          <input
            type="text"
            value={urlDescription}
            onChange={(e) => setUrlDescription(e.target.value)}
            placeholder="Description (optional)"
            className="w-full bg-gray-900 border border-gray-700 rounded-lg px-3 py-2 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:border-transparent text-sm"
          />
          
          <div className="flex justify-end gap-2">
            <button
              type="button"
              onClick={() => {
                setShowUrlInput(false);
                setUrlInput('');
                setUrlDescription('');
              }}
              className="px-3 py-2 text-gray-400 hover:text-gray-200 text-sm transition-colors"
            >
              Cancel
            </button>
            <button
              type="button"
              onClick={handleUrlSubmit}
              disabled={!urlInput.trim()}
              className="px-3 py-2 bg-indigo-600 hover:bg-indigo-500 disabled:opacity-50 text-white rounded-lg text-sm transition-colors"
            >
              Add URL
            </button>
          </div>
        </div>
      )}

      {/* Upload Error */}
      {uploadMutation.isError && (
        <div className="bg-red-900/20 border border-red-800 rounded-xl p-3 flex items-start gap-2">
          <AlertCircle className="h-4 w-4 text-red-400 flex-shrink-0 mt-0.5" />
          <div>
            <p className="text-sm text-red-400">Upload failed</p>
            <p className="text-xs text-red-500 mt-0.5">
              {uploadMutation.error instanceof Error 
                ? uploadMutation.error.message 
                : 'Please try again'}
            </p>
          </div>
        </div>
      )}

      {/* Reference List */}
      {references.length > 0 && (
        <div className="space-y-3">
          <h4 className="text-sm font-medium text-gray-300">
            Added References ({references.length})
          </h4>
          
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
            {references.map((ref, index) => (
              <div
                key={index}
                className="bg-gray-800 border border-gray-700 rounded-lg p-3 flex items-start gap-3"
              >
                <div className="flex-shrink-0">
                  <Image className="h-5 w-5 text-gray-400" />
                </div>
                
                <div className="flex-1 min-w-0">
                  <div className="flex items-start justify-between gap-2">
                    <div className="min-w-0 flex-1">
                      <p className="text-sm text-gray-200 font-medium truncate">
                        {ref.type === 'upload' ? ref.file_name : 'External URL'}
                      </p>
                      {ref.description && (
                        <p className="text-xs text-gray-400 mt-1">
                          {ref.description}
                        </p>
                      )}
                      {ref.type === 'url' && ref.url && (
                        <p className="text-xs text-indigo-400 mt-1 truncate">
                          {ref.url}
                        </p>
                      )}
                    </div>
                    
                    <button
                      type="button"
                      onClick={() => removeReference(index)}
                      className="text-gray-500 hover:text-red-400 transition-colors flex-shrink-0"
                    >
                      <X className="h-4 w-4" />
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default VisualReferences;