import { useRef, useState } from "react";
import { formatBytes, RECEIPT_TYPES, validateReceipt } from "../lib/validation";
import Icon from "./Icon";

export default function UploadField({ file, onFile, error, onError }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  function choose(nextFile) {
    const message = validateReceipt(nextFile);
    if (message) {
      onFile(null);
      onError(message);
      if (inputRef.current) inputRef.current.value = "";
      return;
    }
    onError("");
    onFile(nextFile);
  }

  function handleDrop(event) {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files?.[0] || null);
  }

  function remove(event) {
    event.preventDefault();
    event.stopPropagation();
    onFile(null);
    onError("");
    if (inputRef.current) inputRef.current.value = "";
  }

  return (
    <div className="upload-wrap">
      <input
        ref={inputRef}
        id="receipt"
        className="sr-only"
        type="file"
        accept={RECEIPT_TYPES.join(",")}
        onChange={(event) => choose(event.target.files?.[0] || null)}
      />
      <label
        htmlFor="receipt"
        className={`upload${dragging ? " is-dragging" : ""}${error ? " has-error" : ""}${file ? " has-file" : ""}`}
        onDragOver={(event) => {
          event.preventDefault();
          setDragging(true);
        }}
        onDragLeave={() => setDragging(false)}
        onDrop={handleDrop}
      >
        {file ? (
          <>
            <span className="upload-icon upload-icon-file">
              <Icon name="image" size={24} />
            </span>
            <span className="upload-copy">
              <strong>{file.name}</strong>
              <span>{formatBytes(file.size)} · ready to check</span>
            </span>
            <button
              type="button"
              className="icon-button upload-remove"
              onClick={remove}
              aria-label="Remove screenshot"
            >
              <Icon name="trash" size={17} />
            </button>
          </>
        ) : (
          <>
            <span className="upload-icon">
              <Icon name="upload" size={24} />
            </span>
            <span className="upload-copy">
              <strong>Drop the payment screenshot here</strong>
              <span>or tap to choose a file · JPG or PNG · max 5 MB</span>
            </span>
            <span className="button button-secondary button-sm upload-button">
              Choose file
            </span>
          </>
        )}
      </label>
      {error && (
        <p className="field-error" role="alert">
          <Icon name="alert" size={15} />
          {error}
        </p>
      )}
      <p className="upload-note">
        <Icon name="shield" size={14} />
        Your screenshot is deleted from Khusela within 24 hours.
      </p>
    </div>
  );
}
