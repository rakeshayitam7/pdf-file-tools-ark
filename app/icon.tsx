import { ImageResponse } from 'next/og'

export const size = { width: 64, height: 64 }
export const contentType = 'image/png'

export default function Icon() {
  return new ImageResponse(
    (
      <div
        style={{
          width: '64px',
          height: '64px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          background: '#f4f7fb',
          borderRadius: '14px',
          position: 'relative',
        }}
      >
        <div
          style={{
            width: '36px',
            height: '48px',
            background: 'white',
            border: '2px solid #d7deea',
            borderRadius: '2px',
            position: 'relative',
            display: 'flex',
            alignItems: 'flex-end',
            justifyContent: 'center',
            paddingBottom: '7px',
            color: '#d92d35',
            fontSize: '8px',
            fontWeight: 800,
          }}
        >
          PDF
          <div
            style={{
              position: 'absolute',
              right: '-2px',
              top: '-2px',
              width: '11px',
              height: '11px',
              background: '#e8eef8',
              borderLeft: '2px solid #d7deea',
              borderBottom: '2px solid #d7deea',
            }}
          />
          <div
            style={{
              position: 'absolute',
              right: '-5px',
              top: '17px',
              width: '23px',
              height: '19px',
              color: '#fff',
              background: 'linear-gradient(135deg,#1769ff,#0047d6)',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              fontSize: '16px',
              lineHeight: 1,
              borderRadius: '9px 9px 11px 11px',
            }}
          >
            ♥
          </div>
        </div>
      </div>
    ),
    { ...size }
  )
}