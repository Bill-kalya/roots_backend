--
-- PostgreSQL database dump
--

\restrict u2D85lz6e7xf9qzHNPsBoEucf3M7wOL68MYHfELuPJUtqZSehiyTxK4FAfXf9uQ

-- Dumped from database version 18.4 (Debian 18.4-1.pgdg13+1)
-- Dumped by pg_dump version 18.2

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: conversationtype; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.conversationtype AS ENUM (
    'DIRECT'
);


ALTER TYPE public.conversationtype OWNER TO postgres;

--
-- Name: orderstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.orderstatus AS ENUM (
    'pending',
    'paid',
    'shipped',
    'delivered',
    'cancelled'
);


ALTER TYPE public.orderstatus OWNER TO postgres;

--
-- Name: paymentstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.paymentstatus AS ENUM (
    'pending',
    'completed',
    'failed',
    'cancelled'
);


ALTER TYPE public.paymentstatus OWNER TO postgres;

--
-- Name: userrole; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.userrole AS ENUM (
    'USER',
    'MERCHANT',
    'ADMIN'
);


ALTER TYPE public.userrole OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: alembic_version; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.alembic_version (
    version_num character varying(32) NOT NULL
);


ALTER TABLE public.alembic_version OWNER TO postgres;

--
-- Name: audit_logs; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.audit_logs (
    id uuid NOT NULL,
    user_id uuid,
    action character varying(100) NOT NULL,
    resource character varying(100) NOT NULL,
    resource_id character varying(255),
    details json,
    ip_address character varying(45),
    user_agent character varying(500),
    status character varying(20) NOT NULL,
    error_message character varying(1000),
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.audit_logs OWNER TO postgres;

--
-- Name: conversations; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.conversations (
    id uuid NOT NULL,
    customer_id uuid NOT NULL,
    merchant_id uuid NOT NULL,
    room_id character varying(200) NOT NULL,
    type public.conversationtype NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.conversations OWNER TO postgres;

--
-- Name: merchant_payout_settings; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.merchant_payout_settings (
    id uuid NOT NULL,
    merchant_id uuid NOT NULL,
    payout_method character varying(30) NOT NULL,
    mpesa_phone character varying(20),
    paypal_email character varying(255),
    stripe_account_id character varying(255),
    is_verified boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    mpesa_mode character varying(10) DEFAULT 'PHONE'::character varying NOT NULL,
    mpesa_till_number character varying(20),
    pochi_phone character varying(15)
);


ALTER TABLE public.merchant_payout_settings OWNER TO postgres;

--
-- Name: messages; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.messages (
    id uuid NOT NULL,
    conversation_id uuid NOT NULL,
    sender_id uuid NOT NULL,
    content text NOT NULL,
    status character varying(20) NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    encrypted boolean DEFAULT false NOT NULL
);


ALTER TABLE public.messages OWNER TO postgres;

--
-- Name: newsletter_subscribers; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.newsletter_subscribers (
    id uuid NOT NULL,
    email character varying(255) NOT NULL,
    is_confirmed boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.newsletter_subscribers OWNER TO postgres;

--
-- Name: order_items; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.order_items (
    id uuid NOT NULL,
    order_id uuid NOT NULL,
    product_id uuid NOT NULL,
    name_snapshot character varying(255) NOT NULL,
    price_snapshot numeric(10,2) NOT NULL,
    quantity integer NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.order_items OWNER TO postgres;

--
-- Name: orders; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.orders (
    id uuid NOT NULL,
    user_id uuid NOT NULL,
    status public.orderstatus DEFAULT 'pending'::public.orderstatus,
    subtotal numeric(10,2) NOT NULL,
    shipping_fee numeric(10,2) DEFAULT '0'::numeric,
    total numeric(10,2) NOT NULL,
    payment_provider character varying(50),
    payment_reference character varying(255),
    paid_at timestamp without time zone,
    cancelled_at timestamp without time zone,
    cancellation_reason character varying(255),
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.orders OWNER TO postgres;

--
-- Name: payments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.payments (
    id uuid NOT NULL,
    order_id uuid NOT NULL,
    provider character varying(50) NOT NULL,
    provider_transaction_id character varying(255),
    status public.paymentstatus DEFAULT 'pending'::public.paymentstatus NOT NULL,
    amount numeric(10,2) NOT NULL,
    currency character varying(10) DEFAULT 'KES'::character varying NOT NULL,
    raw_payload text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    checkout_request_id character varying(255),
    phone character varying(20),
    mpesa_receipt character varying(100),
    result_code character varying(10)
);


ALTER TABLE public.payments OWNER TO postgres;

--
-- Name: products; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.products (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    description text NOT NULL,
    long_description text,
    price numeric(10,2) NOT NULL,
    image_url character varying(500) NOT NULL,
    origin character varying(100) NOT NULL,
    tag character varying(100),
    stock integer DEFAULT 0 NOT NULL,
    is_featured boolean DEFAULT false NOT NULL,
    is_active boolean DEFAULT true NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    gallery text[],
    artisan character varying(255),
    weight character varying(100),
    dimensions character varying(100),
    year integer,
    materials text[],
    merchant_id uuid
);


ALTER TABLE public.products OWNER TO postgres;

--
-- Name: receipts; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.receipts (
    id character varying(32) NOT NULL,
    order_id uuid NOT NULL,
    payment_reference character varying(255) NOT NULL,
    payment_method character varying(20) NOT NULL,
    signature character varying(64) NOT NULL,
    canonical_hash character varying(64) NOT NULL,
    subtotal numeric(12,2) NOT NULL,
    shipping_fee numeric(12,2) NOT NULL,
    total numeric(12,2) NOT NULL,
    currency character varying(8) DEFAULT 'KES'::character varying NOT NULL,
    customer_name character varying(255) NOT NULL,
    customer_email character varying(255) NOT NULL,
    payload text NOT NULL,
    status character varying(20) DEFAULT 'paid'::character varying NOT NULL,
    created_at timestamp without time zone NOT NULL
);


ALTER TABLE public.receipts OWNER TO postgres;

--
-- Name: stripe_webhook_events; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.stripe_webhook_events (
    id uuid DEFAULT gen_random_uuid() NOT NULL,
    event_id character varying(255) NOT NULL,
    event_type character varying(255) NOT NULL,
    processed_at timestamp with time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.stripe_webhook_events OWNER TO postgres;

--
-- Name: testimonials; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.testimonials (
    id uuid NOT NULL,
    name character varying(255) NOT NULL,
    text text NOT NULL,
    location character varying(255),
    is_approved boolean DEFAULT false NOT NULL,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    updated_at timestamp without time zone DEFAULT now() NOT NULL
);


ALTER TABLE public.testimonials OWNER TO postgres;

--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id uuid NOT NULL,
    email character varying(255) NOT NULL,
    hashed_password character varying(255) NOT NULL,
    full_name character varying(255) NOT NULL,
    is_active boolean,
    is_verified boolean,
    merchant_approved boolean,
    merchant_details json,
    store_name character varying(255),
    store_description text,
    created_at timestamp without time zone DEFAULT now() NOT NULL,
    role public.userrole NOT NULL,
    verification_token character varying(255),
    failed_login_attempts integer,
    last_failed_login timestamp without time zone,
    account_locked_until timestamp without time zone,
    lockout_reason character varying(255),
    last_login timestamp without time zone,
    last_login_ip character varying(45),
    last_login_user_agent character varying(500),
    password_reset_token character varying(255),
    password_reset_expires timestamp without time zone,
    password_updated_at timestamp without time zone,
    previous_passwords json,
    created_by_ip character varying(45),
    account_created_at timestamp without time zone,
    last_activity timestamp without time zone,
    updated_at timestamp without time zone DEFAULT now() NOT NULL,
    mfa_enabled boolean,
    mfa_secret character varying(255),
    verification_token_expires timestamp without time zone,
    trusted_devices json
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Data for Name: alembic_version; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.alembic_version (version_num) FROM stdin;
3b7c5c7d9f42
a6f6154ec010
\.


--
-- Data for Name: audit_logs; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.audit_logs (id, user_id, action, resource, resource_id, details, ip_address, user_agent, status, error_message, created_at) FROM stdin;
90ea14e9-6b67-43ed-b7ad-56b1a6bd1b3b	\N	login_failed	auth	\N	{"email": "kalyakiprono2003@gmail.com", "reason": "invalid_credentials"}	100.64.0.3	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/148.0.0.0 Safari/537.36	failure	\N	2026-06-10 01:23:06.374941
996fe63c-9802-4b52-a1bf-ed36183b937e	1f923e78-d771-4d8a-b49e-bd86a11ca980	user_register	user	1f923e78-d771-4d8a-b49e-bd86a11ca980	{"email": "kalyakiprono2003@gmail.com"}	\N	\N	success	\N	2026-06-10 01:26:07.249646
e0679d05-2181-47e0-a6d2-7d103b767efe	62c972f9-d4f7-42ae-ab06-88a5685650a0	user_register	user	62c972f9-d4f7-42ae-ab06-88a5685650a0	{"email": "kalyakiprono2003@gmail.com"}	\N	\N	success	\N	2026-06-11 06:35:46.646982
4e97fc2d-c082-460d-9c8a-7833b8b2e1c6	20dd540e-6818-4130-a6b4-b378ca08e3d7	user_register	user	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"email": "kalyakiprono2003@gmail.com"}	\N	\N	success	\N	2026-06-11 12:48:49.498155
fee7b032-3695-4ae7-bac4-7aa424111404	ad25c3b2-9232-46c7-8086-c4a6ac84725b	user_register	user	ad25c3b2-9232-46c7-8086-c4a6ac84725b	{"email": "420.cach3@gmail.com"}	\N	\N	success	\N	2026-06-11 12:53:43.656476
bfdbf5f1-34f5-4c28-b9a7-b1a9db7505ec	8c2eaccb-6d3d-4900-80eb-21f91c2e9724	user_register	user	8c2eaccb-6d3d-4900-80eb-21f91c2e9724	{"email": "420.cach3@gmail.com"}	\N	\N	success	\N	2026-06-23 09:21:26.582498
9ec7de58-d098-40d3-adbd-c3c775b721a1	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "c687abe9-7c06-47d2-9ab8-5c14407a4cbc", "fingerprint": "e46a3b4178ea9fbf98f6f2419fd09b202caa5981ce9c89dddf93f53aea7cd7ef"}	100.64.0.10	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-23 11:14:24.163904
2f34e16f-22a5-4454-9654-7b5f7efae871	8fef6a80-5d4e-45ea-841a-d02608a43ef8	user_register	user	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"email": "billgateskiprono@gmail.com"}	\N	\N	success	\N	2026-06-23 11:35:52.577845
3bfc23e7-1189-44e7-8544-c695d278ee14	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "166b3f30-6e02-4648-b32d-56dfd7471f95", "fingerprint": "e29f01877a14871421088fde796578b3331f19fd7d6e32f8368463698d509a9f"}	100.64.0.18	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-23 11:37:08.677727
64610d86-650d-4f9f-b2ac-6eb7e7471b59	\N	login_failed	auth	\N	{"email": "enivamoraa22@gmail.com", "reason": "invalid_credentials"}	100.64.0.6	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-06-23 12:35:07.114918
f9de9382-7b09-455b-b93c-486b2a893464	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "c45b8785-2a07-4784-9f40-83a29daf3259", "fingerprint": "c8a766ed22f6f4730e2452be3ca769e9a7e679060838fb872a4232ededd2e838"}	100.64.0.8	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-23 12:35:37.331453
247e7e70-14cf-4902-b044-7a50ee11a616	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "5dda772b-edcd-432e-a334-5133d4affd79", "fingerprint": "9dc08614994ce77b50068875517b1cd4c80c2aee0fed0c31c2baf548c9014364"}	100.64.0.13	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-23 18:10:56.18152
222cd132-eb3a-4480-8074-3ff5f81c47a9	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "d38d47c6-3ef5-4c55-a534-5943e80b0611", "fingerprint": "0ddd1d67b83e3f8211e285946f3a2735302d92f742dd2628802d9d11899e81a0"}	100.64.0.12	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-23 18:22:16.88184
306a7965-6516-48ce-aae5-4c009880b0c5	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "d693b60b-494a-4b13-8d8a-93d546a84155", "fingerprint": "5efa4070ea6f200245dcb321ebf47a6859bf6a1d4fb90db08402aab024c9a907"}	100.64.0.5	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-23 18:25:53.846772
b5fed3c5-bd8a-47a0-a401-35549b45df81	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "774eb65a-650e-4037-a9d6-12633f8650cb", "fingerprint": "c9148c228cb645efd161ea7bdd1b1082e1e72b920e56fff51b231497fd410770"}	100.64.0.8	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-23 19:26:54.364173
6c5a74da-e818-4b8c-8de3-527ef74db3ce	8c2eaccb-6d3d-4900-80eb-21f91c2e9724	login_success	auth	8c2eaccb-6d3d-4900-80eb-21f91c2e9724	{"session_id": "01bb1fb4-c697-4996-aa86-bf65c94e58d5", "fingerprint": "f9ce35a12c47fd1135871851f7c46ab6eba9cac4f6ae41c2424762eea5e54aa0"}	100.64.0.12	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-24 05:28:12.36274
cd6e3e9c-822a-4c74-90b0-b97fd77511d7	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "f6109f0e-9e65-46b8-ac91-852d75deed98", "fingerprint": "0ddd1d67b83e3f8211e285946f3a2735302d92f742dd2628802d9d11899e81a0"}	100.64.0.12	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-24 05:29:05.593651
da5b416e-db61-442b-a6b8-a707a0b92238	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "d08ad2c1-81af-4d4c-a65a-6775db4a6e8f", "fingerprint": "9328d5bfeaedf2b56b36d17bc7bafa00d58b994adc5681f412e2f39a7143d1eb"}	100.64.0.18	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-24 05:33:21.58937
295cf183-8076-48d1-b200-f1da3dab112e	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "6c7479be-d7d3-41c7-a473-0ce9fa6631ad", "fingerprint": "ce04ff281ba1f04e77a28073f55c24d502f61abc93b885b2fcb20d989986e2e2"}	100.64.0.7	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-24 16:50:38.625149
50838ffe-734b-4fb8-bf83-c97f5becdd1d	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "ff2b6bc2-0ecd-4b52-ab8c-f85a38348a38", "fingerprint": "fd59e81feed50a15c2363ffccec324d8561e6cea326a8b2bfd6e77a41627bf95"}	100.64.0.16	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-24 19:43:20.631583
795ef821-ba3b-436a-99b0-ea90795a698c	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "c4470cb3-68e3-4e69-bc79-c5c3d6a53151", "fingerprint": "c9148c228cb645efd161ea7bdd1b1082e1e72b920e56fff51b231497fd410770"}	100.64.0.8	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-25 07:16:10.127709
89a66f0e-d836-46b9-89c1-8a68f3d8828e	\N	login_failed	auth	\N	{"email": "kaludavid076@gmail.com", "reason": "invalid_credentials"}	100.64.0.17	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-06-25 09:41:02.048736
594bfacd-79ff-4e34-801c-9c2001b0ef2b	\N	login_failed	auth	\N	{"email": "kaludavid076@gmail.com", "reason": "invalid_credentials"}	100.64.0.15	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-06-25 09:41:22.241548
c17b59f3-e2d0-4d6b-8fe1-9bb377dd60ac	\N	login_failed	auth	\N	{"email": "kaludavid076@gmail.com", "reason": "invalid_credentials"}	100.64.0.15	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-06-25 09:41:26.363482
7c867aa8-9117-48f3-81a1-d1770ca8f982	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "05a05bd7-3d6a-4ac0-99c4-b975f38d9062", "fingerprint": "cab5972a4a627e92dce7cfdb0e3a00d71d3d12b238c57c8e2ef71ca8aca90938"}	100.64.0.15	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-25 09:42:28.234142
a87ba3ed-0152-4e65-bf03-518c993cce5c	29fcab49-a145-4b06-a5f7-785f326871b1	user_register	user	29fcab49-a145-4b06-a5f7-785f326871b1	{"email": "kaludavid076@gmail.com"}	\N	\N	success	\N	2026-06-25 09:43:47.39544
9b3dc44c-a5ae-4a3a-9018-948325a96ffe	29fcab49-a145-4b06-a5f7-785f326871b1	login_failed	auth	\N	{"email": "kaludavid076@gmail.com", "reason": "invalid_credentials"}	100.64.0.10	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-06-25 09:44:37.186193
61697462-ff49-49f7-8586-86b24a132764	29fcab49-a145-4b06-a5f7-785f326871b1	login_success	auth	29fcab49-a145-4b06-a5f7-785f326871b1	{"session_id": "b19ff092-c3da-47fe-9b0f-b161c9d62f1d", "fingerprint": "1f39d2894a9b8719befd1b68ec26351ce04536ca1bd95dc6639739345ba8f46a"}	100.64.0.18	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-25 09:46:30.141979
43af6a42-a357-4f15-9398-6275365ef0b7	29fcab49-a145-4b06-a5f7-785f326871b1	login_failed	auth	\N	{"email": "kaludavid076@gmail.com", "reason": "invalid_credentials"}	100.64.0.3	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-06-25 09:47:34.995562
b47304e1-036e-4aff-8072-0709cae02e8e	29fcab49-a145-4b06-a5f7-785f326871b1	login_failed	auth	\N	{"email": "kaludavid076@gmail.com", "reason": "invalid_credentials"}	100.64.0.9	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-06-25 09:47:38.332592
07432923-0323-49a3-9aaa-fcde7eb2297e	29fcab49-a145-4b06-a5f7-785f326871b1	login_failed	auth	\N	{"email": "kaludavid076@gmail.com", "reason": "invalid_credentials"}	100.64.0.3	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-06-25 09:47:40.314083
f3580274-53ad-4252-977b-3e9524254970	29fcab49-a145-4b06-a5f7-785f326871b1	login_failed	auth	\N	{"email": "kaludavid076@gmail.com", "reason": "invalid_credentials"}	100.64.0.9	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-06-25 09:47:47.951377
27b21459-13a3-4b4e-bfcc-40da349b2d6c	29fcab49-a145-4b06-a5f7-785f326871b1	login_success	auth	29fcab49-a145-4b06-a5f7-785f326871b1	{"session_id": "1133906d-1b86-4247-86ff-ace566e595ae", "fingerprint": "e299eb9e29954a5dcae3bb044f7d8e8bdaece4f4333ca924055c9ac9ac3eb47b"}	100.64.0.14	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-25 09:48:25.619827
aac5172d-b79b-4923-9a61-47761bb7cb5a	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "2fae7b05-e92e-454e-b07b-00cd5c49d945", "fingerprint": "2e9b269d94875bf2c42373f10060239ccc9a87bf0efa7095a80bab32a80406bc"}	100.64.0.9	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-25 09:50:17.614032
7413b024-5951-41ba-b422-a658c5a33b5f	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "126a771f-2bc3-49e0-beb6-e871a4e0fbe3", "fingerprint": "e29f01877a14871421088fde796578b3331f19fd7d6e32f8368463698d509a9f"}	100.64.0.18	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-25 12:52:20.171969
71aae36d-8258-4b6f-8b4c-1bc8cdb21a56	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "5ead905a-bd7e-4248-b0f9-d0c7d704b36e", "fingerprint": "9dc08614994ce77b50068875517b1cd4c80c2aee0fed0c31c2baf548c9014364"}	100.64.0.13	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-25 18:05:32.554021
984d9297-6f18-45fc-9247-e959857bf12e	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "a1549afa-320c-4098-a8d5-44ce8f4a9453", "fingerprint": "194d5066aa70cd9c2560170ef5161573df3eface6a69fb9c3bfd0685d2d6a4de"}	100.64.0.4	Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-25 22:47:05.7581
9b335d5a-38ea-4a3b-9409-312dddc2fd4c	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "4479cfc2-472d-4043-a05b-172b0cf0e06f", "fingerprint": "194d5066aa70cd9c2560170ef5161573df3eface6a69fb9c3bfd0685d2d6a4de"}	100.64.0.4	Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-25 23:38:14.473577
ec7c0e96-bf7f-4217-bab4-75abdf566518	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "9208c3c7-d8a8-4fb8-a2e3-56a503034dad", "fingerprint": "d9f3d8284055c809af51a4d01c876067efd719dc6d22999de883ffcfb8d3f640"}	100.64.0.4	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-26 01:30:49.094646
7d6387d2-eab9-42ee-8158-52dcf082caf8	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "24612ab3-a028-430c-9a26-a3f236a80e2b", "fingerprint": "bd5d2e6beefa7c16bc1b40818c171ba76ed8f704ca7eb1a0b82008372ba787e2"}	100.64.0.14	Mozilla/5.0 (Linux; Android 15; Pixel 9) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-27 19:40:33.647982
9bbc7fe4-af13-4991-bda7-654a533b33ea	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "6d316251-c6e7-42af-aecd-b15c4229455e", "fingerprint": "d9f3d8284055c809af51a4d01c876067efd719dc6d22999de883ffcfb8d3f640"}	100.64.0.4	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-27 22:07:24.137932
c8270322-0281-486f-b599-6a2fb9332dc1	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "b19e1851-7176-4af4-88bb-96db8d89dc3f", "fingerprint": "953b0893ef31b748cf07032d55306409476b4ee8bf064e5e5d6c00b4685cfe4b"}	100.64.0.14	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-06-27 22:40:30.772488
44b003f2-4d68-4f60-83b4-d5c5381757a4	8fef6a80-5d4e-45ea-841a-d02608a43ef8	login_success	auth	8fef6a80-5d4e-45ea-841a-d02608a43ef8	{"session_id": "ea6e9f88-96f6-43c2-8e26-dcc1910682e4", "fingerprint": "d9f3d8284055c809af51a4d01c876067efd719dc6d22999de883ffcfb8d3f640"}	100.64.0.4	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-27 22:43:15.326061
a9cdf3f6-b00f-46fc-9569-193fa8d3afcd	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	user_register	user	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	{"email": "enivamoraa22@gmail.com"}	\N	\N	success	\N	2026-06-28 11:18:57.659689
3fba6fd1-bd8a-4ab1-9ec4-6f376976c1cf	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_success	auth	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	{"session_id": "aeab8ae9-328d-4ad9-b6ca-107e31513fba", "fingerprint": "d061c3f5b2c0315bcd8d567dd9001f8dce1deaefa513b957bf9958b1ee29380f"}	100.64.0.11	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-28 11:19:34.137497
c532eda3-09f5-44ae-a8fe-70f599670ecf	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_success	auth	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	{"session_id": "cafbf5fa-28a0-4bef-ade4-e69609c55c95", "fingerprint": "c84e60e2241be533c82b758f318c811fe3f29a432927c9a633988f69cc016073"}	100.64.0.5	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-28 12:09:20.347592
b3d32c2c-6aa7-4f51-baa1-626c3ede2034	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_success	auth	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	{"session_id": "c9ef6237-94e0-43b3-8372-cb4acda15d0b", "fingerprint": "c84e60e2241be533c82b758f318c811fe3f29a432927c9a633988f69cc016073"}	100.64.0.5	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-28 12:41:24.036771
b5839f03-f9ba-4dbb-a27b-a99a93a73b0b	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "966a4134-d01f-460b-b72b-8826e677cced", "fingerprint": "a6be60a29f62cf477ec54ef333c059d992bc2dd1a861f567b4dc8f2e5cf4307c"}	100.64.0.4	Mozilla/5.0 (iPhone; CPU iPhone OS 18_5 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/18.5 Mobile/15E148 Safari/604.1	success	\N	2026-06-29 10:41:57.945364
120b1b45-d985-4d1f-9e1e-5a6ac0a46da2	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_success	auth	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	{"session_id": "c2cfb10b-d0ec-4cea-ad94-20fc8b70fad3", "fingerprint": "d061c3f5b2c0315bcd8d567dd9001f8dce1deaefa513b957bf9958b1ee29380f"}	100.64.0.11	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-29 22:10:04.478458
35997b11-3a59-470a-98c3-29d72b2fa3cd	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_success	auth	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	{"session_id": "c784b67e-0a18-4715-843d-404add88e45a", "fingerprint": "c474da535c7cd478c29d0945de7968eca2e88b6c9f8e1efe31a60438cae070b4"}	100.64.0.16	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-06-30 11:03:25.558502
e0c0bfee-b377-4c22-85a5-19a5f181244f	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "87bfcfb6-612a-4063-b79f-05076e4d4973", "fingerprint": "1a78ff22c3f30ab2c346848456006d97800ace5cb2701ffc413908622e304167"}	100.64.0.7	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-07-01 00:55:24.877601
cabb02a9-07dc-4af5-9e3b-fb36feefe1db	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_success	auth	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	{"session_id": "a8e13e5f-4107-45fe-89e7-a2c8b6cd4468", "fingerprint": "46666bc028ff5e421bb4978f504d1ade30ca1a7c49e2e3547665e69bc7a250e6"}	100.64.0.4	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	success	\N	2026-07-01 00:57:40.815634
cdf87820-90eb-499c-baac-670b838c06ac	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_failed	auth	\N	{"email": "enivamoraa22@gmail.com", "reason": "invalid_credentials"}	100.64.0.4	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	failure	\N	2026-07-01 01:13:22.150927
ba2a6d6b-a00e-48c3-b4ae-c7e4c1f84d38	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_failed	auth	\N	{"email": "enivamoraa22@gmail.com", "reason": "invalid_credentials"}	100.64.0.4	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	failure	\N	2026-07-01 01:13:32.462514
0e2743d3-d62c-4862-85d0-f57a44932eed	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_failed	auth	\N	{"email": "enivamoraa22@gmail.com", "reason": "invalid_credentials"}	100.64.0.14	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	failure	\N	2026-07-01 01:13:33.915674
a6e3a03a-0918-4b47-879f-a25c8f17ec63	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_failed	auth	\N	{"email": "enivamoraa22@gmail.com", "reason": "invalid_credentials"}	100.64.0.13	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Safari/537.36	failure	\N	2026-07-01 01:14:05.053182
a593acc9-12ae-43ca-8caa-bbcaf4053273	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "f7615778-6511-4953-88d1-d087186206d0", "fingerprint": "46afd380d4b4b2f444fa8c70b5fabaf719c0faa1d60144a12557cee87c411e38"}	100.64.0.14	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36	success	\N	2026-07-02 07:45:17.754211
fdec3c6a-8215-4d44-adf1-979ae34a083c	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	login_success	auth	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	{"session_id": "b3490705-118f-4701-aa2c-587a3a31ac4f", "fingerprint": "f323326794e206660981e975805b9e220002b385d011c195258408b4d36bce05"}	100.64.0.7	Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36	success	\N	2026-07-02 07:46:20.558696
29fa9ee6-51b3-4443-96cf-d05b44ae19f6	20dd540e-6818-4130-a6b4-b378ca08e3d7	login_success	auth	20dd540e-6818-4130-a6b4-b378ca08e3d7	{"session_id": "e74b9811-cfcd-49d0-8339-8970e1c4982a", "fingerprint": "fd59e81feed50a15c2363ffccec324d8561e6cea326a8b2bfd6e77a41627bf95"}	100.64.0.16	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	success	\N	2026-07-02 09:09:25.123689
3cabf545-d357-41fc-8412-834bce53903e	29fcab49-a145-4b06-a5f7-785f326871b1	login_failed	auth	\N	{"email": "kaludavid076@gmail.com", "reason": "invalid_credentials"}	100.64.0.11	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-07-02 09:10:16.56268
ce56f78e-2867-4f69-9295-5a97b3a1c973	29fcab49-a145-4b06-a5f7-785f326871b1	login_failed	auth	\N	{"email": "kaludavid076@gmail.com", "reason": "invalid_credentials"}	100.64.0.11	Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/149.0.0.0 Mobile Safari/537.36	failure	\N	2026-07-02 09:10:18.829086
\.


--
-- Data for Name: conversations; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.conversations (id, customer_id, merchant_id, room_id, type, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: merchant_payout_settings; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.merchant_payout_settings (id, merchant_id, payout_method, mpesa_phone, paypal_email, stripe_account_id, is_verified, created_at, updated_at, mpesa_mode, mpesa_till_number, pochi_phone) FROM stdin;
dfc993b4-fd7c-4279-bff1-c01c7bbccd55	8fef6a80-5d4e-45ea-841a-d02608a43ef8	MPESA	254748623579	\N	\N	f	2026-06-23 18:26:21.224412	2026-06-23 18:26:21.224412	PHONE	\N	\N
\.


--
-- Data for Name: messages; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.messages (id, conversation_id, sender_id, content, status, created_at, updated_at, encrypted) FROM stdin;
\.


--
-- Data for Name: newsletter_subscribers; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.newsletter_subscribers (id, email, is_confirmed, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: order_items; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.order_items (id, order_id, product_id, name_snapshot, price_snapshot, quantity, created_at, updated_at) FROM stdin;
8cafda04-90cd-42a0-a39f-37c0046c90c9	064485d7-a863-4244-a9b9-29d5236776d8	72744c62-ea19-4c2f-92a2-3dd9b0fa24ed	Mwana Pwo mask Chokwe 	0.01	1	2026-06-28 12:41:54.615267	2026-06-28 12:41:54.615267
37bed299-4414-4f34-916d-c22ffa598a65	1154eb99-66b8-4e80-a1f7-846d3bcdbd0e	72744c62-ea19-4c2f-92a2-3dd9b0fa24ed	Mwana Pwo mask Chokwe 	0.01	1	2026-06-29 22:11:03.501078	2026-06-29 22:11:03.501078
93942cf2-e6f1-4d94-a6dc-1dc5aac21f6e	2d07599c-8c19-49db-8957-55f457c3d731	f2ddc32a-0601-42c8-a038-c7b2d0dc6321	Mwana Pwo mask Chokwe 	39.98	1	2026-06-29 22:11:37.990921	2026-06-29 22:11:37.990921
42d10617-8ad3-498e-a3b6-c0321c6e8283	3ef4b710-8f1b-4690-859b-034c8dad4313	72744c62-ea19-4c2f-92a2-3dd9b0fa24ed	Mwana Pwo mask Chokwe 	0.01	1	2026-07-02 07:52:01.367871	2026-07-02 07:52:01.367871
\.


--
-- Data for Name: orders; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.orders (id, user_id, status, subtotal, shipping_fee, total, payment_provider, payment_reference, paid_at, cancelled_at, cancellation_reason, created_at, updated_at) FROM stdin;
064485d7-a863-4244-a9b9-29d5236776d8	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	pending	0.01	0.00	0.01	\N	\N	\N	\N	\N	2026-06-28 12:41:54.615267	2026-06-28 12:41:54.615267
1154eb99-66b8-4e80-a1f7-846d3bcdbd0e	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	pending	0.01	0.00	0.01	\N	\N	\N	\N	\N	2026-06-29 22:11:03.501078	2026-06-29 22:11:03.501078
2d07599c-8c19-49db-8957-55f457c3d731	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	pending	39.98	0.00	39.98	\N	\N	\N	\N	\N	2026-06-29 22:11:37.990921	2026-06-29 22:11:37.990921
3ef4b710-8f1b-4690-859b-034c8dad4313	f3c8c6d0-cea9-45db-a1be-bc1bc0976255	pending	0.01	0.00	0.01	\N	\N	\N	\N	\N	2026-07-02 07:52:01.367871	2026-07-02 07:52:01.367871
\.


--
-- Data for Name: payments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.payments (id, order_id, provider, provider_transaction_id, status, amount, currency, raw_payload, created_at, updated_at, checkout_request_id, phone, mpesa_receipt, result_code) FROM stdin;
\.


--
-- Data for Name: products; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.products (id, name, description, long_description, price, image_url, origin, tag, stock, is_featured, is_active, created_at, updated_at, gallery, artisan, weight, dimensions, year, materials, merchant_id) FROM stdin;
72744c62-ea19-4c2f-92a2-3dd9b0fa24ed	Mwana Pwo mask Chokwe 	An Angolian Protective mask	Mwana Pwo mask Chokwe - is believed to have spiritual protection to the people of angola  .	0.01	https://res.cloudinary.com/djc4y4jft/image/upload/v1782437639/1f3209118e20418b808f974f377fd27c.webp	Angola	rare	1	t	t	2026-06-26 01:33:59.049188	2026-06-26 01:33:59.049188	{}	kofi mile	1200g	30x40x3cm	2019	{wood}	8fef6a80-5d4e-45ea-841a-d02608a43ef8
f2ddc32a-0601-42c8-a038-c7b2d0dc6321	Mwana Pwo mask Chokwe 	An Angolian Protective mask	An angolian protective mask belied to protect  villages from bad spirits	39.98	https://res.cloudinary.com/djc4y4jft/image/upload/v1782589406/58b69583da4d49ae8a0fe3889f078438.webp	Angola 	Curved	1	f	t	2026-06-27 19:43:25.519687	2026-06-27 22:08:57.001666	{}	Bill Kalya	1200g	30x10x4cm	2024	{wood}	8fef6a80-5d4e-45ea-841a-d02608a43ef8
\.


--
-- Data for Name: receipts; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.receipts (id, order_id, payment_reference, payment_method, signature, canonical_hash, subtotal, shipping_fee, total, currency, customer_name, customer_email, payload, status, created_at) FROM stdin;
\.


--
-- Data for Name: stripe_webhook_events; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.stripe_webhook_events (id, event_id, event_type, processed_at) FROM stdin;
\.


--
-- Data for Name: testimonials; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.testimonials (id, name, text, location, is_approved, created_at, updated_at) FROM stdin;
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, email, hashed_password, full_name, is_active, is_verified, merchant_approved, merchant_details, store_name, store_description, created_at, role, verification_token, failed_login_attempts, last_failed_login, account_locked_until, lockout_reason, last_login, last_login_ip, last_login_user_agent, password_reset_token, password_reset_expires, password_updated_at, previous_passwords, created_by_ip, account_created_at, last_activity, updated_at, mfa_enabled, mfa_secret, verification_token_expires, trusted_devices) FROM stdin;
8fef6a80-5d4e-45ea-841a-d02608a43ef8	billgateskiprono@gmail.com	$2b$12$Dm2BIuXIZ7x2.orP7Ucvy.SJo1pvPawAxUxJ2A1q2PiFHeTP1skc.	Billgates Kiprono	t	t	t	\N	\N	\N	2026-06-23 11:35:51.917726	MERCHANT	\N	0	\N	\N	\N	2026-06-27 22:43:15.293607	\N	\N	\N	\N	\N	[]	\N	2026-06-23 11:35:52.253989	2026-06-27 22:43:15.294095	2026-06-27 22:43:15.051132	f	\N	\N	\N
8c2eaccb-6d3d-4900-80eb-21f91c2e9724	420.cach3@gmail.com	$2b$12$GxEpYIY/bMOlvORuaTBCtO6i0uheFVc/Vf7xL.LxBnjYEfhyPQKiS	Bill kalya	t	t	f	\N	\N	\N	2026-06-23 09:21:26.062702	USER	\N	0	\N	\N	\N	2026-06-24 05:28:12.313319	\N	\N	\N	\N	\N	[]	\N	2026-06-23 09:21:26.2919	2026-06-24 05:28:12.314361	2026-06-24 05:28:12.102466	f	\N	\N	\N
f3c8c6d0-cea9-45db-a1be-bc1bc0976255	enivamoraa22@gmail.com	$2b$12$OpWbR/ANpf2A8zv83jzJ0OzlhZS/3LGbutEUu3ErdeRk9X19DZb0q	Eniva Moraa	t	t	f	\N	\N	\N	2026-06-28 11:18:56.956022	USER	\N	0	\N	\N	\N	2026-07-02 07:46:20.500829	\N	\N	\N	\N	\N	[]	\N	2026-06-28 11:18:57.187612	2026-07-02 07:46:20.501559	2026-07-02 07:46:20.269078	f	\N	\N	[]
20dd540e-6818-4130-a6b4-b378ca08e3d7	kalyakiprono2003@gmail.com	$2b$12$PDf5i2YRZjnIIkl40jhBJ.djfdzR45PHcgnI.bpHL6yCB3Ln2C4eq	Bill Kalya	t	t	f	\N	\N	\N	2026-06-11 12:46:33.888819	ADMIN	\N	0	\N	\N	\N	2026-07-02 09:09:25.070726	\N	\N	\N	\N	\N	[]	\N	2026-06-11 12:46:34.259858	2026-07-02 09:09:25.07263	2026-07-02 09:09:24.843288	f	\N	\N	\N
\.


--
-- Name: alembic_version alembic_version_pkc; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.alembic_version
    ADD CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num);


--
-- Name: audit_logs audit_logs_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.audit_logs
    ADD CONSTRAINT audit_logs_pkey PRIMARY KEY (id);


--
-- Name: conversations conversations_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_pkey PRIMARY KEY (id);


--
-- Name: merchant_payout_settings merchant_payout_settings_merchant_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.merchant_payout_settings
    ADD CONSTRAINT merchant_payout_settings_merchant_id_key UNIQUE (merchant_id);


--
-- Name: merchant_payout_settings merchant_payout_settings_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.merchant_payout_settings
    ADD CONSTRAINT merchant_payout_settings_pkey PRIMARY KEY (id);


--
-- Name: messages messages_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_pkey PRIMARY KEY (id);


--
-- Name: newsletter_subscribers newsletter_subscribers_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.newsletter_subscribers
    ADD CONSTRAINT newsletter_subscribers_email_key UNIQUE (email);


--
-- Name: newsletter_subscribers newsletter_subscribers_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.newsletter_subscribers
    ADD CONSTRAINT newsletter_subscribers_pkey PRIMARY KEY (id);


--
-- Name: order_items order_items_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT order_items_pkey PRIMARY KEY (id);


--
-- Name: orders orders_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT orders_pkey PRIMARY KEY (id);


--
-- Name: payments payments_order_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_order_id_key UNIQUE (order_id);


--
-- Name: payments payments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_pkey PRIMARY KEY (id);


--
-- Name: payments payments_provider_transaction_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT payments_provider_transaction_id_key UNIQUE (provider_transaction_id);


--
-- Name: products products_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_pkey PRIMARY KEY (id);


--
-- Name: receipts receipts_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT receipts_pkey PRIMARY KEY (id);


--
-- Name: stripe_webhook_events stripe_webhook_events_event_id_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stripe_webhook_events
    ADD CONSTRAINT stripe_webhook_events_event_id_key UNIQUE (event_id);


--
-- Name: stripe_webhook_events stripe_webhook_events_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.stripe_webhook_events
    ADD CONSTRAINT stripe_webhook_events_pkey PRIMARY KEY (id);


--
-- Name: testimonials testimonials_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.testimonials
    ADD CONSTRAINT testimonials_pkey PRIMARY KEY (id);


--
-- Name: conversations uq_conversation_customer_merchant; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT uq_conversation_customer_merchant UNIQUE (customer_id, merchant_id);


--
-- Name: conversations uq_conversation_room_id; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT uq_conversation_room_id UNIQUE (room_id);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: idx_audit_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_created_at ON public.audit_logs USING btree (created_at);


--
-- Name: idx_audit_resource; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_resource ON public.audit_logs USING btree (resource, resource_id);


--
-- Name: idx_audit_user_action; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_audit_user_action ON public.audit_logs USING btree (user_id, action);


--
-- Name: idx_merchant_payout_settings_merchant_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX idx_merchant_payout_settings_merchant_id ON public.merchant_payout_settings USING btree (merchant_id);


--
-- Name: ix_conversations_room_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_conversations_room_id ON public.conversations USING btree (room_id);


--
-- Name: ix_messages_conversation_created_at; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_messages_conversation_created_at ON public.messages USING btree (conversation_id, created_at);


--
-- Name: ix_messages_conversation_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_messages_conversation_id ON public.messages USING btree (conversation_id);


--
-- Name: ix_newsletter_subscribers_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_newsletter_subscribers_email ON public.newsletter_subscribers USING btree (email);


--
-- Name: ix_payments_checkout_request_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_payments_checkout_request_id ON public.payments USING btree (checkout_request_id);


--
-- Name: ix_payments_order_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_payments_order_id ON public.payments USING btree (order_id);


--
-- Name: ix_payments_status; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_payments_status ON public.payments USING btree (status);


--
-- Name: ix_products_merchant_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_products_merchant_id ON public.products USING btree (merchant_id);


--
-- Name: ix_receipts_canonical_hash; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_receipts_canonical_hash ON public.receipts USING btree (canonical_hash);


--
-- Name: ix_receipts_customer_email; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_receipts_customer_email ON public.receipts USING btree (customer_email);


--
-- Name: ix_receipts_order_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_receipts_order_id ON public.receipts USING btree (order_id);


--
-- Name: ix_users_email_lower_unique; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX ix_users_email_lower_unique ON public.users USING btree (lower((email)::text));


--
-- Name: uq_receipts_payment_reference; Type: INDEX; Schema: public; Owner: postgres
--

CREATE UNIQUE INDEX uq_receipts_payment_reference ON public.receipts USING btree (payment_reference);


--
-- Name: conversations conversations_customer_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_customer_id_fkey FOREIGN KEY (customer_id) REFERENCES public.users(id);


--
-- Name: conversations conversations_merchant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.conversations
    ADD CONSTRAINT conversations_merchant_id_fkey FOREIGN KEY (merchant_id) REFERENCES public.users(id);


--
-- Name: order_items fk_order_items_order_id_orders; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT fk_order_items_order_id_orders FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: order_items fk_order_items_product_id_products; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.order_items
    ADD CONSTRAINT fk_order_items_product_id_products FOREIGN KEY (product_id) REFERENCES public.products(id);


--
-- Name: orders fk_orders_user_id_users; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.orders
    ADD CONSTRAINT fk_orders_user_id_users FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: payments fk_payments_order_id_orders; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.payments
    ADD CONSTRAINT fk_payments_order_id_orders FOREIGN KEY (order_id) REFERENCES public.orders(id);


--
-- Name: receipts fk_receipts_order_id_orders; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.receipts
    ADD CONSTRAINT fk_receipts_order_id_orders FOREIGN KEY (order_id) REFERENCES public.orders(id) ON DELETE RESTRICT;


--
-- Name: messages messages_conversation_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_conversation_id_fkey FOREIGN KEY (conversation_id) REFERENCES public.conversations(id) ON DELETE CASCADE;


--
-- Name: messages messages_sender_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.messages
    ADD CONSTRAINT messages_sender_id_fkey FOREIGN KEY (sender_id) REFERENCES public.users(id);


--
-- Name: products products_merchant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.products
    ADD CONSTRAINT products_merchant_id_fkey FOREIGN KEY (merchant_id) REFERENCES public.users(id) ON DELETE SET NULL;


--
-- PostgreSQL database dump complete
--

\unrestrict u2D85lz6e7xf9qzHNPsBoEucf3M7wOL68MYHfELuPJUtqZSehiyTxK4FAfXf9uQ

