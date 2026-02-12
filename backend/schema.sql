USE [chatbot]
GO

/****** Object:  Table [dbo].[messages]    Script Date: 10/29/2025 4:13:51 PM ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[messages](
	[message_id] [uniqueidentifier] NOT NULL,
	[session_id] [uniqueidentifier] NOT NULL,
	[turn_number] [int] NOT NULL,
	[timestamp] [datetimeoffset](7) NULL,
	[user_prompt] [nvarchar](max) NOT NULL,
	[rewritten_user_prompt] [nvarchar](max) NULL,
	[classified_intent] [varchar](50) NULL,
	[mistral_intent] [varchar](50) NULL,
	[tinyllama_intent] [varchar](50) NULL,
	[bert_intent] [varchar](50) NULL,
	[chatbot_response] [nvarchar](max) NOT NULL,
	[generated_sql] [nvarchar](max) NULL,
	[unique_sources] [varchar](512) NULL,
	[rag_chunks] [nvarchar](max) NULL,
PRIMARY KEY CLUSTERED 
(
	[message_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY]
GO

ALTER TABLE [dbo].[messages] ADD  DEFAULT (newid()) FOR [message_id]
GO

ALTER TABLE [dbo].[messages] ADD  DEFAULT (sysdatetimeoffset()) FOR [timestamp]
GO

ALTER TABLE [dbo].[messages]  WITH CHECK ADD FOREIGN KEY([session_id])
REFERENCES [dbo].[sessions] ([session_id])
GO


USE [chatbot]
GO

/****** Object:  Table [dbo].[sessions]    Script Date: 10/29/2025 4:43:02 PM ******/
SET ANSI_NULLS ON
GO

SET QUOTED_IDENTIFIER ON
GO

CREATE TABLE [dbo].[sessions](
	[session_id] [uniqueidentifier] NOT NULL,
	[start_time] [datetimeoffset](7) NULL,
	[end_time] [datetimeoffset](7) NULL,
PRIMARY KEY CLUSTERED 
(
	[session_id] ASC
)WITH (PAD_INDEX = OFF, STATISTICS_NORECOMPUTE = OFF, IGNORE_DUP_KEY = OFF, ALLOW_ROW_LOCKS = ON, ALLOW_PAGE_LOCKS = ON, OPTIMIZE_FOR_SEQUENTIAL_KEY = OFF) ON [PRIMARY]
) ON [PRIMARY]
GO

ALTER TABLE [dbo].[sessions] ADD  DEFAULT (sysdatetimeoffset()) FOR [start_time]
GO


--=============

USE [chatbot];
GO

/****** Object:  Table [dbo].[feedback]    Script Date: 2025-11-04  ******/
SET ANSI_NULLS ON;
GO

SET QUOTED_IDENTIFIER ON;
GO

CREATE TABLE [dbo].[feedback](
    [feedback_id] UNIQUEIDENTIFIER NOT NULL DEFAULT (NEWID()),
    [message_id] UNIQUEIDENTIFIER NOT NULL,           -- Links feedback to a message
    [session_id] UNIQUEIDENTIFIER NOT NULL,           -- Useful if you want to filter feedback by session
    [feedback_type] VARCHAR(10) NOT NULL,             -- e.g. 'like' or 'dislike'
    [comment] NVARCHAR(MAX) NULL,                     -- Optional user text
    [timestamp] DATETIMEOFFSET(7) NOT NULL DEFAULT (SYSDATETIMEOFFSET()),

    CONSTRAINT [PK_feedback] PRIMARY KEY CLUSTERED ([feedback_id] ASC),

    CONSTRAINT [FK_feedback_messages] FOREIGN KEY ([message_id])
        REFERENCES [dbo].[messages] ([message_id]) ON DELETE CASCADE,

    CONSTRAINT [FK_feedback_sessions] FOREIGN KEY ([session_id])
        REFERENCES [dbo].[sessions] ([session_id]) ON DELETE CASCADE,

    CONSTRAINT [CK_feedback_type] CHECK ([feedback_type] IN ('like', 'dislike'))
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY];
GO
