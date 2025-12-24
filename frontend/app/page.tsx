'use client';

import { useState } from 'react';
import { useRouter } from 'next/navigation';
import { uploadCSV, LeagueResponse } from '@/lib/api';

export default function Home() {
  const router = useRouter();
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [dragActive, setDragActive] = useState(false);

  const handleDrag = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    if (e.type === 'dragenter' || e.type === 'dragover') {
      setDragActive(true);
    } else if (e.type === 'dragleave') {
      setDragActive(false);
    }
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setDragActive(false);

    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      handleFile(e.dataTransfer.files[0]);
    }
  };

  const handleFile = (selectedFile: File) => {
    if (!selectedFile.name.endsWith('.csv')) {
      setError('Please select a CSV file');
      return;
    }
    setFile(selectedFile);
    setError(null);
  };

  const handleFileInput = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      handleFile(e.target.files[0]);
    }
  };

  const handleUpload = async () => {
    if (!file) return;

    setUploading(true);
    setError(null);

    try {
      console.log('Starting upload...');
      const response: LeagueResponse = await uploadCSV(file);
      console.log('Upload response:', response);
      console.log('League ID:', response.id);

      // Store league ID and navigate to chat
      localStorage.setItem('leagueId', response.id);
      router.push(`/chat?leagueId=${response.id}`);
    } catch (err: any) {
      console.error('Upload error:', err);
      console.error('Error response:', err.response);
      setError(err.response?.data?.detail || 'Failed to upload CSV. Please try again.');
      setUploading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-razzball-secondary to-razzball-primary">
      <div className="container mx-auto px-4 py-12">
        {/* Header */}
        <div className="text-center mb-12">
          <h1 className="text-5xl font-bold text-white mb-4">
            Fantasy Baseball Chatbot
          </h1>
          <p className="text-xl text-white/90">
            Powered by Razzball.com
          </p>
          <p className="text-lg text-white/80 mt-2">
            Upload your league CSV and get AI-powered recommendations
          </p>
        </div>

        {/* Upload Card */}
        <div className="max-w-2xl mx-auto">
          <div className="card">
            <h2 className="text-2xl font-bold mb-6 text-gray-800">
              Upload Your League CSV
            </h2>

            {/* Drag and Drop Zone */}
            <div
              className={`relative border-2 border-dashed rounded-lg p-12 text-center transition-colors ${
                dragActive
                  ? 'border-razzball-primary bg-orange-50'
                  : 'border-gray-300 hover:border-razzball-primary'
              }`}
              onDragEnter={handleDrag}
              onDragLeave={handleDrag}
              onDragOver={handleDrag}
              onDrop={handleDrop}
            >
              <input
                type="file"
                accept=".csv"
                onChange={handleFileInput}
                className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                disabled={uploading}
              />

              <div className="space-y-4">
                <svg
                  className="mx-auto h-16 w-16 text-gray-400"
                  stroke="currentColor"
                  fill="none"
                  viewBox="0 0 48 48"
                >
                  <path
                    d="M28 8H12a4 4 0 00-4 4v20m32-12v8m0 0v8a4 4 0 01-4 4H12a4 4 0 01-4-4v-4m32-4l-3.172-3.172a4 4 0 00-5.656 0L28 28M8 32l9.172-9.172a4 4 0 015.656 0L28 28m0 0l4 4m4-24h8m-4-4v8m-12 4h.02"
                    strokeWidth={2}
                    strokeLinecap="round"
                    strokeLinejoin="round"
                  />
                </svg>

                {file ? (
                  <div>
                    <p className="text-lg font-semibold text-gray-700">{file.name}</p>
                    <p className="text-sm text-gray-500 mt-1">
                      {(file.size / 1024).toFixed(1)} KB
                    </p>
                  </div>
                ) : (
                  <div>
                    <p className="text-lg text-gray-600">
                      Drag and drop your CSV file here
                    </p>
                    <p className="text-sm text-gray-500 mt-1">
                      or click to browse
                    </p>
                  </div>
                )}
              </div>
            </div>

            {/* Supported Formats */}
            <div className="mt-6 p-4 bg-blue-50 rounded-lg">
              <h3 className="font-semibold text-blue-900 mb-2">Supported Formats:</h3>
              <ul className="text-sm text-blue-800 space-y-1">
                <li>• Fantrax League Player File</li>
                <li>• CBS Sports League Export</li>
                <li>• NFBC League Player File</li>
              </ul>
            </div>

            {/* Error Message */}
            {error && (
              <div className="mt-4 p-4 bg-red-50 border border-red-200 rounded-lg">
                <p className="text-red-800">{error}</p>
              </div>
            )}

            {/* Upload Button */}
            <button
              onClick={handleUpload}
              disabled={!file || uploading}
              className="btn-primary w-full mt-6"
            >
              {uploading ? 'Uploading...' : 'Upload & Start Chat'}
            </button>
          </div>

          {/* How It Works */}
          <div className="mt-8 text-white">
            <h3 className="text-xl font-bold mb-4">How it works:</h3>
            <ol className="space-y-2">
              <li>1. Export your league roster as a CSV from Fantrax, CBS Sports, or NFBC</li>
              <li>2. Upload the CSV file using the form above</li>
              <li>3. Chat with our AI assistant to get personalized fantasy baseball advice</li>
              <li>4. Get recommendations on pickups, drops, and roster strategy</li>
            </ol>
          </div>
        </div>
      </div>
    </div>
  );
}
