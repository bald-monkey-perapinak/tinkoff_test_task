import { useRef } from 'react';

interface Props {
  onFileSelect: (file: File) => void;
  isLoading: boolean;
}

export function FileUpload({ onFileSelect, isLoading }: Props) {
  const inputRef = useRef<HTMLInputElement>(null);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    const file = e.dataTransfer.files[0];
    if (file) onFileSelect(file);
  };

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) onFileSelect(file);
  };

  return (
    <div className="section">
      <div
        className="upload-zone"
        onDragOver={(e) => e.preventDefault()}
        onDrop={handleDrop}
        onClick={() => inputRef.current?.click()}
      >
        <div className="upload-zone-icon">↑</div>
        <div className="upload-zone-text">
          {isLoading ? 'Загрузка...' : 'Перетащите файл или нажмите для выбора'}
        </div>
        <div className="upload-zone-hint">.json / .csv</div>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".json,.csv"
        onChange={handleChange}
        style={{ display: 'none' }}
      />
    </div>
  );
}
