import Button from '@/components/ui/button';
import Image from '@/components/ui/image';
import { Card, CardContent, IconButton } from '@mui/material';
import { red } from '@mui/material/colors';
import { GridCloseIcon } from '@mui/x-data-grid';
import CheckIcon from '@mui/icons-material/Check';
import FiberNewIcon from '@mui/icons-material/FiberNew';

type DatasetItemProp = {
  imgSrc: string;
  label: number;
  unique_id: string;
  isDeleted?: boolean;
  onClose?: (unique_id: string) => void;
  onImageClick?: (imageUrl: string) => void;
  onLabelChange?: (unique_id: string, label: number) => void;
};
const DatasetItem = ({
  imgSrc,
  label,
  unique_id,
  isDeleted,
  onClose,
  onImageClick,
  onLabelChange,
}: DatasetItemProp) => {
  const handleSelect = (buttonValue: number) => {
    if (label === buttonValue) {
      onLabelChange?.(unique_id, -1);
    } else {
      onLabelChange?.(unique_id, buttonValue);
    }
  };
  let bg = 'white';
  if (label === 0) bg = 'bg-green-200';
  else if (label === 1) bg = 'bg-red-200';
  return (
    <Card>
      <CardContent
        className={bg}
        sx={{
          paddingTop: 6,
          position: 'relative',
        }}
      >
        <div
          className={`${!isDeleted ? 'hidden ' : ''}absolute inset-0 bg-gray-500 bg-opacity-50 z-10`}
        ></div>
        <div
          style={{
            display: isDeleted !== undefined ? 'None' : undefined,
            position: 'absolute',
            left: 16,
            top: 16,
          }}
        >
          <FiberNewIcon color="primary" />
        </div>
        <IconButton
          className="border"
          aria-label="close"
          style={{ position: 'absolute', right: 8, top: 8 }}
          color="primary"
          sx={{ color: red[500], zIndex: 11 }}
          onClick={() => onClose?.(unique_id)}
        >
          <GridCloseIcon />
        </IconButton>
        <div
          className="relative group cursor-pointer"
          onClick={() => onImageClick?.(imgSrc)}
        >
          <Image
            src={imgSrc}
            alt="データセット画像"
            className="w-full h-auto shadow-md rounded-lg mb-2"
          />
          <div className="absolute inset-0 shadow-md rounded-lg bg-black opacity-0 group-hover:opacity-10 transition-opacity duration-300"></div>
        </div>

        <div className="flex flex-row">
          <Button
            onClick={() => handleSelect(0)}
            sx={{
              marginRight: 1,
              bgcolor: 'success.main',
              color: 'success.contrastText',
              '&:hover': {
                bgcolor: 'success.dark',
              },
            }}
          >
            OK
            {label === 0 && (
              <CheckIcon className="absolute top-1/2 left-1/4 transform -translate-x-1/2 -translate-y-1/2" />
            )}
          </Button>
          <Button
            onClick={() => handleSelect(1)}
            sx={{
              bgcolor: 'error.main',
              color: 'error.contrastText',
              '&:hover': {
                bgcolor: 'error.dark',
              },
            }}
          >
            NG
            {label === 1 && (
              <CheckIcon className="absolute top-1/2 left-1/4 transform -translate-x-1/2 -translate-y-1/2" />
            )}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
};

export default DatasetItem;
